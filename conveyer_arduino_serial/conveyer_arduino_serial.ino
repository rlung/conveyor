// Whisker Stimulator Controller
// Randall Ung
//
// Use with Python GUI "session_control.py". Handles hardware for control of
// behavioral session, particularly whisker stimulation and imaging.
// 
// Parameters for session are received via serial connection and Python GUI. 
// Data from hardware is routed directly back via serial connection to Python 
// GUI for recording and calculations. 
// 
// Parameters from serial:
//  0: csplus_num
//  1: csminus_num
//  2: presession
//  3: postsession
//  4: prestim
//  5: poststim
//  6: uniformDistro
//  7: meanITI
//  8: minITI
//  9: maxITI
// 10: csplus_dur
// 11: csplus_freq
// 12: csminus_dur
// 13: csminus_freq
// 14: imaging TTL
//
// Output codes:
//  0: End session
//  1: Onset of stimulation
//  2: Offset of stimulation
//  3: Time to start of next trial, planned (used to mark next trial time)
//  4: Time of CS+ trial start, actual (used as recorded trial time)
//  5: Time of CS- trial start, actual
//  6: Length of session
//  7: Tracking values
//  8: Lick onset timestamp
//  9: Lick offset timestamp
// 10: Solenoid onset timestamp
// 11: Solenoid offset timestamp
//
// Input (serial) codes:
//  0 (48): End session
//  E (69): Start session


#include "Waveform.h"
#define DELIM ","               // Delimiter used for serial outputs
#define STEPSCALE 2             // Scale factor to convert tracking to stepper


// Pins
const int imgStartPin = 6;
const int imgStopPin  = 7;
const int csPin = 4;
const int lickPin = 5;
const int solPin = 8;
const int railStartPin = 9;
const int railStopPin = 10;
const int trackPinA   = 2;
const int trackPinB   = 3;

// Output codes
const int code_end = 0;
const int code_conveyer_steps = 1;
const int code_next_trial = 3;
const int code_trial_onset = 4;
const int code_session_length = 6;
const int code_track = 7;
const int code_lick_onset = 8;
const int code_lick_offset = 9;
const int code_solenoid_onset = 10;
const int code_solenoid_offset = 11;

// Variables via serial
unsigned long preSession;
unsigned long postSession;
int trialNum;
unsigned long trialDur;
boolean uniformDistro;
unsigned long meanITI;
unsigned long minITI;
unsigned long maxITI;
unsigned long tsEnd;
int csDur;                  // Duration (ms) of one whisker stimulation
int csFreq;                 // Frequency of piezo bender
int solDur;
boolean imageAll;
int trackPeriod;

// Other variables
unsigned long sampleDelay;
unsigned long* trials;          // Pointer to array for DMA; initialized later
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

  delete [] trials;
  unsigned long trials = 0;

  while (1);
}


// Retrieve parameters from serial
void updateParams() {
  const int paramNum = 13;
  unsigned long parameters[paramNum];
  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  preSession      = parameters[0];
  postSession     = parameters[1];
  trialNum        = parameters[2];
  trialDur        = parameters[3];
  uniformDistro   = parameters[4];
  meanITI         = parameters[5];
  minITI          = parameters[6];
  maxITI          = parameters[7];
  csDur           = parameters[8];
  csFreq          = parameters[9];
  solDur          = parameters[10];
  imageAll        = parameters[11];
  trackPeriod     = parameters[12];
}


void genTrials() {
  // Create ITIs
  // ITIs can be created uniformly or exponentially. Set by
  // variable 'uniformDistro'.
  
  // Timestamp of last trial during trial list creation. Initially defined as
  // delay to first trial (preSession).
  unsigned long lastTrial = preSession;
  
  if (uniformDistro) {
    // Create ITIs with a uniform distribution
    // All ITIs are the same value defined by meanITI

    for (int tt = 0; tt < trialNum; tt++) {
      trials[tt] = lastTrial + meanITI;
      lastTrial = trials[tt];
    }
  }
  else {
    // Create ITIs with an exponential distribution
    // ITIs are on average close to meanITI and constrained by minITI &
    // maxITI. Distribution is created and values less than minITI are
    // instead defined as minITI.
    // 
    // If max:mean ITI is 3:1, actual mean ITI is ~0.84 of "meanITI"

    float u;
    float exponent = (float)maxITI / meanITI;
    float minFactor = (float)minITI / meanITI;
    float randFactor;
    unsigned long ITI;

    for (int tt = 0; tt < trialNum; tt++) {
      // randFactor is calculated exponential function of u with integral [0, 1] 
      // approximately equal to 1 for large maxITI/meanITI and small 
      // minITI/meanITI. Thus average value is approximately 1 with max value 
      // of maxITI.
      u = (float) random(0, 10000) / 10000;
      float randFactor1 = 1 - exp(-(float)exponent);   // Casting unnecessary?
      float randFactor2 = -log(1 - randFactor1 * u);
      randFactor = randFactor2 + minFactor;
      ITI = meanITI * randFactor;

      trials[tt] = (unsigned long) lastTrial + ITI;  // Casting unnecessary?
      lastTrial = trials[tt];
    }
  }
}


void waitForStart() {
  const byte code_end = '0';
  const byte code_start = 'E';

  while (1) {
    byte reading = Serial.read();
    switch(reading) {
      case 48:
        endSession(0);
      case 69:
        return;   // Start session
    }
  }
}


void setup() {
  Serial.begin(9600);
  Serial1.begin(9600);
  randomSeed(analogRead(0));

  // Set pins
  pinMode(imgStartPin, OUTPUT);
  pinMode(imgStopPin, OUTPUT);
  pinMode(solPin, OUTPUT);
  pinMode(railStartPin, INPUT);
  pinMode(railStopPin, INPUT);
  pinMode(trackPinA, INPUT);
  pinMode(trackPinB, INPUT);

  // Set interrupt
  attachInterrupt(digitalPinToInterrupt(trackPinA), track, RISING);

  // Wait for parameters from serial
  Serial.println("conveyer_arduino\n"
                 "Waiting for parameters to load.");
  while (Serial.available() <= 0);
  updateParams();

  // Create trials
  trials = new () unsigned long[trialNum];  // Allocate memory
  genTrials();
  tsEnd = trials[trialNum-1] + trialDur;

  // Wait for start signal
  Serial.println("Waiting for start signal ('E').");
  waitForStart();

  // Print timestamp of first trial and length of session
  Serial.print(code_session_length);
  Serial.print(DELIM);
  Serial.print(0);
  Serial.print(DELIM);
  Serial.println(tsEnd);
  
  Serial.print(code_next_trial);
  Serial.print(DELIM);
  Serial.println(trials[0]);

  // Start imaging if whole session is imaged
  if (imageAll) digitalWrite(imgStartPin, HIGH);
}


void loop() {
  // Record start of session
  static unsigned long start = millis();

  // Variables
  static unsigned long imgStartTS;      // Timestamp pin was last on
  static unsigned long imgStopTS;
  static const int imgPinDur = 100;     // Druation of imaging TTL to scope
  static const int trackPeriod = 50;
  static unsigned long nextTrackTS = trackPeriod;
  static int nextTrial;
  static boolean running = true;        // Indicates trials are still in process
  static boolean inTrial = false;       // Indicates if within trial
  static boolean imaging = false;       // Indicates imaging TTL state
  static boolean stimming = false;      // Indicates stimming state
  static boolean resetConveyer;
  static const byte stepCode = 51;      // Code to signal slave--should be number not attainable by other bytes sent

  static int trialLicks;
  static const int trialLicksLimit = 5;

  // Get timestamp of current loop
  unsigned long ts = millis() - start;

  // Turn off events.
  if (ts >= imgStartTS + imgPinDur) digitalWrite(imgStartPin, LOW);
  if (ts >= imgStopTS + imgPinDur) digitalWrite(imgStopPin, LOW);

  // -- 0. TRACK MOVEMENT -- //
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

      if (inTrial && 
          trackOutVal > 0 &&
          !digitalRead(railStopPin)) {
        // The number of steps on the motor is proportional to the distance moved
        // from tracking. The speed is set so that the number of steps will take
        // the amount of time between each read of track value (ie, trackPeriod).

        byte steps2take = trackOutVal >> STEPSCALE;
        
        // Speed calculation based on 50-ms track interval and 200 steps/rotation.
        // Calculation: rot/min = steps(steps2take) / interval(50ms) * 60000 ms/min / steps/rot(200)
        // Max number of steps in constrained by byte max (255) and max allowed 
        // for step speed (assuming speed = steps * 6 thus 255/6 = 42).
        byte stepSpeed = steps2take * 6;
        
        if (steps2take > 42) {
          steps2take = 42;
          stepSpeed = 255;
        }
        
        Serial.print(code_conveyer_steps);
        Serial.print(DELIM);
        Serial.print(ts);
        Serial.print(DELIM);
        Serial.println(steps2take);

        Serial1.write(stepCode);
        Serial1.write(stepSpeed);
        Serial1.write(steps2take);
      }
    }
    
    // Reset timer
    nextTrackTS = nextTrackTS + trackPeriod;   // Increment nextTrackTS.
  }

  // -- 1. SERIAL SCAN -- //
  if (Serial.available() > 0) {
    byte reading = Serial.read();
    switch(reading) {
      case 48:
        endSession(ts);
        break;
    }
  }

  if (Serial1.available() > 0) {
    static String serialMsg;

    char serialRecv = Serial1.read();
    serialMsg += serialRecv;

    if (serialRecv == '\n') {
      Serial.print(serialMsg);
      serialMsg = "";
    }
  }

  // -- 2. SESSION TIMING -- //
  if (running) {
    // 'running' defines that trials are left in session.
    
    // Begin trial
    if (!inTrial && (ts >= trials[nextTrial])) {
      // Beginning of trial (before stim)
      inTrial = true;

      // Start imaging if by trial and not already started
      if (!imageAll && !imaging) {
        digitalWrite(imgStartPin, HIGH);
        imgStartTS = ts;
        imaging = true;
      }

      // Tone to start trial
      tone(csPin, csFreq, csDur);

      // Print trial start time
      Serial.print(code_trial_onset);
      Serial.print(DELIM);
      Serial.println(ts);
    }

    // End of trial
    // Ends on either time limit or lick limit.
    else if (inTrial && 
             (ts >= (trials[nextTrial] + trialDur) ||
              trialLicks >= trialLicksLimit)) {
      trialLicks = 0;
      inTrial = false;
      resetConveyer = true;
      
      if (!imageAll && imaging) {
        digitalWrite(imgStopPin, HIGH);
        imgStopTS = ts;
        imaging = false;
      }

      if (nextTrial < trialNum - 1) {
        // For all trials except last, increment trial index and send time to
        // next trial via serial.
        nextTrial++;
        Serial.print(code_next_trial);
        Serial.print(DELIM);
        Serial.println(trials[nextTrial] - ts);
      }
      else {
        // For last trial
        running = false;
        Serial.print(code_next_trial);
        Serial.print(DELIM);
        Serial.println("0");        // Indicates no more trials left.
      }
    }
  }
  else {
    // Check if time limit on session has been reached.
    if (ts >= tsEnd) endSession(ts);
  }
  
  // -- 3. RESET CONVEYER -- //
  // Need to make sure reset is fast enough to finish before next trial
  static unsigned long nextResetTS;
  
  if (resetConveyer) {
    // Stop when end of rail reached
    if (digitalRead(railStartPin)) {
      resetConveyer = false;
    }
    else {
      if (ts >= nextResetTS) {
        Serial.print(255);
        Serial.print(DELIM);
        Serial.println(255);

        Serial1.write(stepCode);
        Serial1.write(255);
        Serial1.write(255);
        
        nextResetTS = ts + trackPeriod;
      }
    }
  }

  // -- 4. LICKING -- //
  static boolean lickPrev;
  static boolean solenoidOn;
  static unsigned long solTS;

  // Record lick state
  boolean lick = digitalRead(lickPin);

  // Turn off solenoid after set time
  if (solenoidOn & (ts >= solTS + solDur) ) {
    solenoidOn = false;
    digitalWrite(solPin, LOW);

    Serial.print(code_solenoid_offset);
    Serial.print(DELIM);
    Serial.println(ts);
  }

  // Record licks
  if (lick & !lickPrev) {
    Serial.print(code_lick_onset);
    Serial.print(DELIM);
    Serial.println(ts);

    // Record trial lick
    if (inTrial) trialLicks++;

    if (inTrial &&
        !solenoidOn) {
      solenoidOn = true;
      solTS = ts;
      digitalWrite(solPin, HIGH);

      Serial.print(code_solenoid_onset);
      Serial.print(DELIM);
      Serial.println(ts);
    }
  }
  else if (!lick & lickPrev) {
    Serial.print(code_lick_offset);
    Serial.print(DELIM);
    Serial.println(ts);
  }

  lickPrev = lick;
}

