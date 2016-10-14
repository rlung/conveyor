// Free roam conveyer
// Randall Ung
//
// <description>


#include "Waveform.h"
#define ENDCODE 48
#define STARTCODE 69
#define DELIM ","         // Delimiter used for serial outputs
#define STEPCODE 53
#define STEPMAX 127       // Maximum number of steps by stepper


// Pins
const int imgStartPin = 6;
const int imgStopPin  = 7;
const int speakerPin = 4;
const int ledPin = 13;
const int railStartPin = 9;
const int railStopPin = 10;
const int trackPinA   = 2;
const int trackPinB   = 3;

// Output codes
const int code_end = 0;
const int code_conveyer_steps = 1;
const int code_rail_end = 2;
const int code_session_length = 6;
const int code_track = 7;

// Variables via serial
unsigned long session;
unsigned long preSession;
unsigned long postSession;
unsigned long tsEnd;
unsigned int cueDur;
unsigned int cueFreq;
boolean imageAll;
unsigned int trackPeriod;   // Time between stepper readings
unsigned int stepThresh;    // Minimum track movements for stepper to move
unsigned int stepShift;     // Bit shift to scale track steps to stepper steps

// Other variables
volatile int trackChange = 0;   // Rotations within tracking epochs


void track() {
  // Track changes in rotary encoder via interrupt
  if (digitalRead(trackPinB)) trackChange++;
  else trackChange--;
}


void endSession(unsigned long ts) {
  // Send "end" signal
  Serial.print(code_end);
  Serial.print(DELIM);
  Serial.println(ts);
  digitalWrite(imgStopPin, HIGH);

  // Reset pins
  digitalWrite(imgStartPin, LOW);
  delay(100);
  digitalWrite(imgStopPin, LOW);
  digitalWrite(ledPin, LOW);
  noTone(speakerPin);

  while (1);
}


// Retrieve parameters from serial
void updateParams() {
  const int paramNum = 9;
  unsigned long parameters[paramNum];
  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  session      = parameters[0];
  preSession   = parameters[1];
  postSession  = parameters[2];
  cueDur       = parameters[3];
  cueFreq      = parameters[4];
  imageAll     = parameters[5];
  trackPeriod  = parameters[6];
  stepThresh   = parameters[7];
  stepShift    = parameters[8];
}


void waitForStart() {
  const byte code_end = '0';
  const byte code_start = 'E';

  while (1) {
    byte reading = Serial.read();
    switch(reading) {
      case ENDCODE:
        endSession(0);
      case STARTCODE:
        return;   // Start session
    }
  }
}


void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);
  randomSeed(analogRead(0));

  // Set pins
  pinMode(ledPin, OUTPUT);
  pinMode(imgStartPin, OUTPUT);
  pinMode(imgStopPin, OUTPUT);
  pinMode(railStartPin, INPUT);
  pinMode(railStopPin, INPUT);
  pinMode(trackPinA, INPUT);
  pinMode(trackPinB, INPUT);

  // Wait for parameters from serial
  Serial.println("conveyer_arduino\n"
                 "Waiting for parameters to load.");
  while (Serial.available() <= 0);
  updateParams();
  tsEnd = preSession + session + postSession;

  // Wait for start signal
  Serial.println("Waiting for start signal ('E').");
  waitForStart();

  // Set interrupt
  attachInterrupt(digitalPinToInterrupt(trackPinA), track, RISING);

  // Print timestamp of first trial and length of session
  Serial.print(code_session_length);
  Serial.print(DELIM);
  Serial.print(0);
  Serial.print(DELIM);
  Serial.println(tsEnd);

  // Start imaging if whole session is imaged
  if (imageAll) digitalWrite(imgStartPin, HIGH);
}


void loop() {
  // Record start of session
  static const unsigned long start = millis();

  // Variables
  static unsigned long imgStartTS;      // Timestamp pin was last on
  static unsigned long imgStopTS;
  static unsigned long nextTrackTS = trackPeriod;
  static unsigned long nextResetTS;
  static boolean inSession;
  static boolean endOfRail;             // Indicates end of conveyer rail reached
  static boolean resetConveyer;

  // Get timestamp of current loop
  unsigned long ts = millis() - start;

  // -- SESSION CONTROL -- //
  // -- 0. SERIAL SCAN -- //
  if (Serial.available() > 0) {
    // Watch for information from computer.
    byte reading = Serial.read();
    switch(reading) {
      case ENDCODE:
        endSession(ts);
        break;
    }
  }

  if (Serial1.available() > 1) {
    // Transmit step data from Arduino slave.
    if (Serial1.read() == STEPCODE) {  // Throw out first byte
      Serial.print(code_conveyer_steps);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(Serial1.read());
    }
  }

  // -- 1. SESSION TIMING -- //
  if (ts >= preSession &&
      ts <  preSession + session) {
    inSession = true;

    if (endOfRail &&
        ts >= nextResetTS) {
      resetConveyer = true;
    }
  }
  else if (ts >= preSession + session) {
    inSession = false;
    resetConveyer = true;
  }
  else if (ts >= tsEnd) {
    endSession(ts);
  }
  
  
  // -- 2. TRACK MOVEMENT -- //
  if (!endOfRail &&
      digitalRead(railStopPin)) {
    // End of track reached
    endOfRail = true;
    nextResetTS = ts + trackPeriod;

    // Relay to computer
    Serial.print(code_rail_end);
    Serial.print(DELIM);
    Serial.println(ts);
  }

  if (ts >= nextTrackTS) {
    int trackOutVal = trackChange;
    trackChange = 0;
    
    if (trackOutVal != 0) {
      // Print tracking valeus otherwise.
      Serial.print(code_track);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(trackOutVal);

      if (inSession &&
          trackOutVal > stepThresh &&
          !resetConveyer &&
          !endOfRail) {
        
        byte steps2take = trackOutVal >> stepShift;
        if (steps2take > STEPMAX) {
          steps2take = STEPMAX;
        }

        Serial1.write((byte)STEPCODE);
        Serial1.write(trackPeriod);
        Serial1.write(steps2take);
      }
    }
    
    // Reset timer
    nextTrackTS = nextTrackTS + trackPeriod;   // Increment nextTrackTS.
  }
  
  // -- 3. RESET CONVEYER -- //
  // Need to make sure reset is fast enough to finish before next trial
  
  if (resetConveyer) {
    // Stop when start of rail reached
    if (digitalRead(railStartPin)) {
      resetConveyer = false;
      tone(speakerPin, cueFreq, cueDur);
    }
    else {
      if (ts >= nextResetTS) {
        Serial1.write((byte)STEPCODE);
        Serial1.write((byte)0);
        Serial1.write((byte)0);  // This value doesn't really matter
      }
    }
  }
}

