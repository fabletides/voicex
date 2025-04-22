#include <Arduino.h>
#include <driver/adc.h>
#include <soc/sens_reg.h>
#include <driver/dac.h>

#define MIC_PIN 36
#define MOTOR1_PIN 25
#define MOTOR2_PIN 26
#define LED_PIN 2
#define POT_PIN 34

#define PWM_RESOLUTION 8
#define PWM_CHANNEL_1 0
#define PWM_CHANNEL_2 1

#define BUFFER_SIZE 256
#define SAMPLE_RATE 8000
#define THRESHOLD_MIN 100
#define THRESHOLD_MAX 2000

#define FILTER_ALPHA 0.2

int16_t audioBuffer[BUFFER_SIZE];
int bufferIndex = 0;
bool isActive = false;
int currentThreshold = 500;
float filteredValue = 0;
unsigned long lastActivity = 0;
unsigned long lastFreqUpdate = 0;

int baseFrequency = 100;
int modFrequency = 200;
int freqRange = 100;

void setupPWM() {
  ledcSetup(PWM_CHANNEL_1, baseFrequency, PWM_RESOLUTION);
  ledcSetup(PWM_CHANNEL_2, modFrequency, PWM_RESOLUTION);
  ledcAttachPin(MOTOR1_PIN, PWM_CHANNEL_1);
  ledcAttachPin(MOTOR2_PIN, PWM_CHANNEL_2);
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(POT_PIN, INPUT);
  
  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(ADC1_CHANNEL_0, ADC_ATTEN_DB_11);
  
  setupPWM();
  
  ledcWrite(PWM_CHANNEL_1, 0);
  ledcWrite(PWM_CHANNEL_2, 0);
  
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(100);
  }
  
  Serial.println("VoiceX initialized");
}

void loop() {
  readMicrophone();
  processSoundData();
  
  if (millis() - lastFreqUpdate > 100) {
    detectFrequencies();
    lastFreqUpdate = millis();
  }
  
  if (POT_PIN != -1) {
    int potValue = analogRead(POT_PIN);
    currentThreshold = map(potValue, 0, 4095, THRESHOLD_MIN, THRESHOLD_MAX);
  }
  
  static unsigned long lastDebugTime = 0;
  if (millis() - lastDebugTime > 1000) {
    Serial.print("DEBUG:");
    Serial.print(millis());
    Serial.print(",");
    Serial.print(currentThreshold);
    Serial.print(",");
    Serial.print(isActive);
    Serial.print(",");
    Serial.print(baseFrequency);
    Serial.print(",");
    Serial.println(modFrequency);
    
    lastDebugTime = millis();
  }
  
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    processCommand(command);
  }
}

void readMicrophone() {
  int rawValue = adc1_get_raw(ADC1_CHANNEL_0);
  audioBuffer[bufferIndex] = rawValue;
  bufferIndex = (bufferIndex + 1) % BUFFER_SIZE;
  filteredValue = FILTER_ALPHA * rawValue + (1 - FILTER_ALPHA) * filteredValue;
}

void processSoundData() {
  int intensity = getSoundIntensity();
  
  if (intensity > currentThreshold) {
    if (!isActive) {
      Serial.println("SPEECH_START");
    }
    isActive = true;
    lastActivity = millis();
    digitalWrite(LED_PIN, HIGH);
    
    int normalizedIntensity = map(intensity, currentThreshold, currentThreshold * 3, 50, 255);
    normalizedIntensity = constrain(normalizedIntensity, 50, 255);
    int secondIntensity = normalizedIntensity * 0.8;
    
    setVibrationIntensity(normalizedIntensity, secondIntensity);
    updateVibrationPattern();
  }
  else if (isActive && (millis() - lastActivity > 200)) {
    unsigned long duration = millis() - lastActivity;
    Serial.print("SPEECH_END:");
    Serial.println(duration);
    
    isActive = false;
    digitalWrite(LED_PIN, LOW);
    
    for (int i = 255; i >= 0; i -= 10) {
      setVibrationIntensity(i, i * 0.8);
      delay(5);
    }
    
    setVibrationIntensity(0, 0);
  }
}

int getSoundIntensity() {
  int64_t sum = 0;
  int16_t maxVal = -32768;
  int16_t minVal = 32767;
  
  for (int i = 0; i < BUFFER_SIZE; i++) {
    int16_t value = audioBuffer[i];
    sum += value;
    if (value > maxVal) maxVal = value;
    if (value < minVal) minVal = value;
  }
  
  int16_t average = sum / BUFFER_SIZE;
  int16_t range = maxVal - minVal;
  
  return range;
}

float simpleFilter(float newValue, float oldValue, float alpha) {
  return alpha * newValue + (1 - alpha) * oldValue;
}

void updateVibrationPattern() {
  if (isActive) {
    unsigned long currentTime = millis();
    float phaseOffset = sin(currentTime * 0.001) * 0.2;
    
    int adjustedBase = baseFrequency * (1.0 + phaseOffset);
    int adjustedMod = modFrequency * (1.0 - phaseOffset);
    
    setMotorFrequency(PWM_CHANNEL_1, adjustedBase);
    setMotorFrequency(PWM_CHANNEL_2, adjustedMod);
  }
}

void detectFrequencies() {
  if (!isActive) return;
  
  int zeroCrossings = 0;
  int16_t prevSample = audioBuffer[0];
  
  for (int i = 1; i < BUFFER_SIZE; i++) {
    int16_t currentSample = audioBuffer[i];
    if ((prevSample < 2048 && currentSample >= 2048) || 
        (prevSample >= 2048 && currentSample < 2048)) {
      zeroCrossings++;
    }
    prevSample = currentSample;
  }
  
  int estimatedFreq = zeroCrossings * SAMPLE_RATE / 2 / BUFFER_SIZE;
  estimatedFreq = constrain(estimatedFreq, 70, 350);
  
  baseFrequency = estimatedFreq;
  modFrequency = estimatedFreq * 1.5;
  
  setMotorFrequency(PWM_CHANNEL_1, baseFrequency);
  setMotorFrequency(PWM_CHANNEL_2, modFrequency);
}

void setMotorFrequency(uint8_t channel, int freq) {
  ledcSetup(channel, freq, PWM_RESOLUTION);
}

void setVibrationIntensity(uint8_t intensity1, uint8_t intensity2) {
  ledcWrite(PWM_CHANNEL_1, intensity1);
  ledcWrite(PWM_CHANNEL_2, intensity2);
}

void processCommand(String command) {
  int colonIndex = command.indexOf(':');
  if (colonIndex != -1) {
    String cmd = command.substring(0, colonIndex);
    String values = command.substring(colonIndex + 1);
    
    if (cmd == "CONFIG") {
      int commaIndex = values.indexOf(',');
      if (commaIndex != -1) {
        String param = values.substring(0, commaIndex);
        int value = values.substring(commaIndex + 1).toInt();
        
        if (param == "threshold") {
          currentThreshold = value;
        }
        else if (param == "base_frequency") {
          baseFrequency = value;
        }
        else if (param == "mod_frequency") {
          modFrequency = value;
        }
        else if (param == "filter_alpha") {
          FILTER_ALPHA = value / 100.0;
        }
      }
    }
    else if (cmd == "PLAY_PHRASE") {
      // Placeholder for phrase playback functionality
      // Could be implemented with preset vibration patterns
      String phraseId = values;
      Serial.print("Playing phrase: ");
      Serial.println(phraseId);
    }
  }
}