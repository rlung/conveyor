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
#define CODESTOP 48
#define CODEFORWARD 49
#define CODEBACKWARD 50
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
// unsigned long sessionDur;
unsigned long pre_session;
unsigned long post_session;
unsigned long trial_num;
unsigned long trial_duration;
unsigned long iti;
unsigned long img_all;
unsigned long img_ttl_dur;
unsigned long track_period;
unsigned long track_steps;

// Other variables
unsigned long ts_next_trial;
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
  delay(IMGPINDUR);
  digitalWrite(imgStopPin, LOW);

  while (1);
}


// Retrieve parameters from serial
void getParams() {
  const int paramNum = 9;
  unsigned long parameters[paramNum];

  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  pre_session = parameters[0];
  post_session = parameters[1];
  trial_num = parameters[2];
  trial_duration = parameters[3];
  iti = parameters[4];
  img_all = parameters[5];
  img_ttl_dur = parameters[6];
  track_period = parameters[7];
  track_steps = parameters[8];
}


void waitForStart() {
  byte reading;

  while (1) {
    reading = Serial.read();
    switch(reading) {
      case CODEEND:
        Serial.println("Serial end session");
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
  Serial.println("Conveyor\n"
                 "Waiting for parameters...");
  while (Serial.available() <= 0);
  getParams();
  Serial.println("Paremeters processed.");

  // Wait for start signal
  Serial.println("Waiting for start signal ('E').");
  waitForStart();
  Serial.println("Session starting");

  // Set interrupt
  // Do not set earlier as track() will be called before session starts.
  attachInterrupt(digitalPinToInterrupt(trackPinA), track, RISING);
  digitalWrite(imgStartPin, HIGH);
}


void loop() {

  // Variables
  static unsigned long imgStartTS;      // Timestamp pin was last on
  static unsigned long imgStopTS;
  static boolean imaging;               // Indicates imaging TTL state
  static boolean conveyorSet;
  static unsigned long nextTrackTS = track_period;  // Timer used for motion tracking and conveyor movement

  static unsigned long ts_next_trial = pre_session + iti;
  static unsigned int trial_ix;

  static boolean manual;       // indicates if trial was started manually
  static boolean in_trial;
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
    }
  }

  
  // -- 1. SESSION CONTROL -- //
  if (ts > ts_next_trial && ! in_trial) {
    in_trial = true;
    move2mouse = true;

    Serial.print(code_rail_leave);
    Serial.print(DELIM);
    Serial.println(ts);

    Serial1.write((byte)CODEFORWARD)

    trial_ix++;
    if (trial_ix < trial_num) ts_next_trial += iti;
  }

  // Start trial
  if (in_trial) {

    // Move conveyor toward subject
    if (move2mouse) {
      if (digitalRead(railEndPin)) {
        move2mouse = false;
        actualTrial = true;
        trialStart = ts;

        Serial.print(code_trial_start);
        Serial.print(DELIM);
        Serial.print(ts);
        Serial.print(DELIM);
        Serial.println(manual);

        Serial1.write((byte)CODESTOP);
      }
    }

    // Actual trial
    else if (actualTrial) {
      // End trial
      if (ts - trialStart >= trial_duration) {
        actualTrial = false;
        move2start = true;
        Serial.println("Trial over");

        Serial1.write((byte)CODEBACKWARD);
      }
    }

    // Move conveyor back to start
    else if (move2start) {
      if (digitalRead(railStartPin)) {
        move2start = false;
        in_trial = false;
        manual = false;

        Serial.print(code_rail_home);
        Serial.print(DELIM);
        Serial.println(ts);

        Serial1.write((byte)CODESTOP)
      }
    }
  }

  // End session
  else if (trial_ix >= trial_num && ! in_trial && ts >= ts_next_trial + post_session) {
    Serial.println(trial_num);
    Serial.println(trial_ix);
    Serial.println(in_trial);
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
    nextTrackTS = nextTrackTS + track_period;
  }
}
