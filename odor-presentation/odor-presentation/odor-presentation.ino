/*
Odor presentation

Use with Python GUI "odor-presentation.py". Handles hardware for control of
behavioral session.

Parameters for session are received via serial connection and Python GUI. 
Data from hardware is routed directly back via serial connection to Python 
GUI for recording and calculations.
*/


#define IMGPINDUR 100
#define CODEEND 48
#define STARTCODE 69
#define CODETRIAL 70
#define DELIM ","         // Delimiter used for serial outputs
#define STEPSHIFT 1       // Scale factor to convert tracking to stepper
#define STEPCODE 53
#define STEPMAX 127       // Maximum number of steps by stepper


// Pins
const int trackPinA   = 2;
const int trackPinB   = 3;
const int imgStartPin = 6;
const int imgStopPin  = 7;
const int railStartPin = 9;
const int railEndPin = 10;

//int railStart = true;
//int railEnd = false;

// Output codes
const int code_end = 0;
const int code_conveyer_steps = 1;
const int code_trial_start = 3;
// const int code_trial_man = 4;
const int code_rail_leave = 5;
const int code_rail_home = 6;
const int code_track = 7;

// Variables via serial
unsigned long sessionDur;
unsigned long trialDur;
unsigned int trackPeriod;

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

  while (1);
}


// Retrieve parameters from serial
void getParams() {
  const int paramNum = 3;
  unsigned long parameters[paramNum];

  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }
  sessionDur   = parameters[0];
  trialDur     = parameters[1];
  trackPeriod  = parameters[2];
}


void waitForStart() {
  byte reading;

  while (1) {
    reading = Serial.read();
    switch(reading) {
      case CODEEND:
        endSession(0);
      case STARTCODE:
        return;   // Start session
    }
  }
}


void setup() {
  Serial.begin(9600);         // used to communicate with computer
  Serial1.begin(9600);        // used to communicate with conveyor motor
  randomSeed(analogRead(0));

  // Set pins
  pinMode(imgStartPin, OUTPUT);
  pinMode(imgStopPin, OUTPUT);
  pinMode(railStartPin, INPUT);
  pinMode(railEndPin, INPUT);
  pinMode(trackPinA, INPUT);
  pinMode(trackPinB, INPUT);

  // Wait for parameters from serial
  Serial.println("odor-presentation\n"
                 "Waiting for parameters...");
  while (Serial.available() <= 0);
  getParams();
  Serial.println("Paremeters processed.");

  // Wait for start signal
  Serial.println("Waiting for start signal ('E').");
  waitForStart();

  // Set interrupt
  // Do not set earlier as track() will be called before session starts.
  attachInterrupt(digitalPinToInterrupt(trackPinA), track, RISING);
  Serial.println("Start!");
}


void loop() {

  // Variables
  static unsigned long imgStartTS;      // Timestamp pin was last on
  static unsigned long imgStopTS;
  static boolean imaging;               // Indicates imaging TTL state
  static boolean conveyorSet;
  static unsigned long nextTrackTS = trackPeriod;  // Timer used for motion tracking and conveyor movement

  static boolean manual:       // indicates if trial was started manually
  static boolean trialState;
  static boolean move2mouse;
  static boolean actualTrial;
  static boolean move2start;
  static unsigned long trialStart;

  // Timestamp
  static const unsigned long start = millis();  // record start of session
  unsigned long ts = millis() - start;          // current timestamp

  // Turn off events.
  if (ts >= imgStartTS + IMGPINDUR) digitalWrite(imgStartPin, LOW);
  if (ts >= imgStopTS + IMGPINDUR) digitalWrite(imgStopPin, LOW);


  // -- SESSION CONTROL -- //

  // -- 0. SERIAL SCAN -- //
  // Read from computer
  if (Serial.available() > 0) {
    // Watch for information from computer.
    byte reading = Serial.read();
    switch(reading) {
      case CODEEND:
        endSession(ts);
        break;
      case CODETRIAL:
        trialState = true;
        move2mouse = true;
        manual = true;
        // Serial.print(code_trial_man);
        // Serial.print(DELIM);
        // Serial.println(ts);
        break;
//      case 56:
//        railStart = false;
//        railEnd = true;
//        Serial.println("At mouse");
//        break;
//      case 57:
//        railStart = true;
//        railEnd = false;
//        Serial.println("At home");
//        break;
      break;
    }
  }

  // Read from conveyor Arduino
  if (Serial1.available() > 1) {
    // Transmit step data from Arduino slave to computer.
    if (Serial1.read() == STEPCODE) {  // Throw out first byte
      Serial.print(code_conveyer_steps);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(Serial1.read());
    }
  }
  
  // -- 1. SESSION CONTROL -- //

  // Start trial
  if (trialState) {

    // Move conveyor toward subject
    if  (move2mouse) {
//      if (railEnd) {
      if (digitalRead(railEndPin)) {
        move2mouse = false;
        actualTrial = true;
        trialStart = ts;

        Serial.print(code_trial_start);
        Serial.print(DELIM);
        Serial.print(ts);
        Serial.print(DELIM);
        Serial.println(manual);
      }
      else {
        if (ts >= nextTrackTS) {
          Serial1.write((byte)STEPCODE);
          Serial1.write((byte)50);
          Serial1.write((byte)25);  // This value doesn't really matter
        }
      }
    }

    // Actual trial
    else if (actualTrial) {
      // End trial
      if (ts - trialStart >= trialDur) {
        actualTrial = false;
        move2start = true;
        Serial.println("Trial over");
      }
    }

    // Move conveyor back to start
    else if (move2start) {
//      if (railStart) {
      if (digitalRead(railStartPin)) {
        move2start = false;
        trialState = false;
        manual = false;

        Serial.print(code_rail_home);
        Serial.print(DELIM);
        Serial.println(ts);
      }
      else {
        if (ts >= nextTrackTS) {
          Serial1.write((byte)STEPCODE);
          Serial1.write((byte)0);
          Serial1.write((byte)0);
        }
      }
    }
  }

  // End session
  else if (ts >= sessionDur) {
    endSession(ts);
  }


  // -- 2. TRACK MOVEMENT -- //

  if (ts >= nextTrackTS) {
    int trackOutVal = trackChange;
    trackChange = 0;
    
    if (trackOutVal != 0) {
      Serial.print(code_track);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(trackOutVal);
    }
    
    // Increment nextTractTS for next track stamp
    nextTrackTS = nextTrackTS + trackPeriod;
  }
}
