// Whisker Stimulator Controller
// Randall Ung
//
// Use with Python GUI "session_control.py". Handles hardware for control of
// behavioral session, particularly whisker stimulation and imaging.
// 
// Parameters for session are received via serial connection and Python GUI. 
// Data from hardware is routed directly back via serial connection to Python 
// GUI for recording and calculations. 


#include "Waveform.h"
#define IMGPINDUR 100
#define ENDCODE 48
#define STARTCODE 69
#define DELIM ","         // Delimiter used for serial outputs
#define STEPSCALE 1       // Scale factor to convert tracking to stepper
#define STEPCODE 53
#define STEPMAX 255       // Maximum number of steps by stepper


// Pins
const int imgStartPin = 6;
const int imgStopPin  = 7;
const int csPin = 4;
const int ledPin = 13;
const int railStartPin = 9;
const int railStopPin = 10;
const int trackPinA   = 2;
const int trackPinB   = 3;

// Output codes
const int code_end = 0;
const int code_conveyer_steps = 1;
const int code_rail_end = 2;
const int code_next_trial = 3;
const int code_trial_onset_csplus = 4;
const int code_trial_onset_csminus = 5;
const int code_session_length = 6;
const int code_track = 7;

// Variables via serial
unsigned int csplusNum;
unsigned int csminusNum;
unsigned long preSession;
unsigned long postSession;
unsigned int trialNum;
unsigned long trialDur;
boolean uniformDistro;
unsigned long meanITI;
unsigned long minITI;
unsigned long maxITI;
unsigned long tsEnd;
unsigned int csplusDur;             // Duration (ms) of one whisker stimulation
unsigned int csplusFreq;                 // Frequency of piezo bender
unsigned int csminusDur;
unsigned int csminusFreq;
boolean imageAll;
unsigned int trackPeriod;

// Other variables
unsigned long sampleDelay;
unsigned long* trials;          // Pointer to array for DMA; initialized later
boolean* csplus_trials;
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
  noTone(csPin);

  delete [] trials;
  unsigned long trials = 0;

  while (1);
}


// Retrieve parameters from serial
void updateParams() {
  const int paramNum = 15;
  unsigned long parameters[paramNum];
  for (int p = 0; p < paramNum; p++) {
    parameters[p] = Serial.parseInt();
  }

  csplusNum       = parameters[0];
  csminusNum      = parameters[1];
  preSession      = parameters[2];
  postSession     = parameters[3];
  trialDur        = parameters[4];
  uniformDistro   = parameters[5];
  meanITI         = parameters[6];
  minITI          = parameters[7];
  maxITI          = parameters[8];
  csplusDur       = parameters[9];
  csplusFreq      = parameters[10];
  csminusDur      = parameters[11];
  csminusFreq     = parameters[12];
  imageAll        = parameters[13];
  trackPeriod     = parameters[14];

  trialNum = csplusNum + csminusNum;
}


void genTrials() {
  // Create ITIs
  // ITIs can be created uniformly or exponentially. Set by
  // variable 'uniformDistro'.
  
  // Timestamp of last trial during trial list creation. Initially defined as
  // delay to first trial (preSession).
  unsigned long lastTrial = preSession;

  // Set first trial at 0
  trials[0] = preSession;

  if (uniformDistro) {
    // Create ITIs with a uniform distribution
    // All ITIs are the same value defined by meanITI

    for (int tt = 1; tt < trialNum; tt++) {
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

    for (int tt = 1; tt < trialNum; tt++) {
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


void shufflePlusMinus() {
  // Shuffle CS+ & CS- trials
  // Create array of 'true' & 'false' with amount corresponding to CS+ & CS- 
  // trials. Shuffle created array to randomize presentation of CS+ & CS- 
  // trials.

  // Boolean array with: number of "true" == number of CS+ trials (csplusNum)
  for (int tt = 0; tt < trialNum; tt++) {
    if (tt < csplusNum) csplus_trials[tt] = true;
    else csplus_trials[tt] = false;
  }

  // Shuffle boolean array
  for (int tt = 0; tt < trialNum - 1; tt++) {
    int rr = random(tt, trialNum - 1);
    boolean temp = csplus_trials[tt];
    csplus_trials[tt] = csplus_trials[rr];
    csplus_trials[rr] = temp;
  }
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
  pinMode(imgStartPin, OUTPUT);
  pinMode(imgStopPin, OUTPUT);
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
  tsEnd = trials[trialNum-1] + trialDur + postSession;

  // Shuffle CS+ & CS- trials
  csplus_trials = new () boolean[trialNum];
  shufflePlusMinus();

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
  static const unsigned long start = millis();

  // Variables
  static unsigned long imgStartTS;      // Timestamp pin was last on
  static unsigned long imgStopTS;
  static unsigned long nextTrackTS = trackPeriod;
  static unsigned int nextTrial;
  static boolean running = true;        // Indicates trials are still in process
  static boolean inTrial;               // Indicates if within trial
  static boolean imaging;               // Indicates imaging TTL state
  static boolean stimming;              // Indicates stimming state
  static boolean endOfRail;             // Indicates end of conveyer rail reached
  static boolean resetConveyer;

  // Get timestamp of current loop
  unsigned long ts = millis() - start;

  // Turn off events.
  if (ts >= imgStartTS + IMGPINDUR) digitalWrite(imgStartPin, LOW);
  if (ts >= imgStopTS + IMGPINDUR) digitalWrite(imgStopPin, LOW);

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
    // Tranmit step data from Arduino slave.
    if (Serial1.read() == STEPCODE) {  // Throw out first byte
      Serial.print(code_conveyer_steps);
      Serial.print(DELIM);
      Serial.print(ts);
      Serial.print(DELIM);
      Serial.println(Serial1.read());
    }
  }

  // -- 1. SESSION TIMING -- //
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

      // Cues
      if (csplus_trials[nextTrial]) {
        tone(csPin, csplusFreq, csplusDur);
      }
      else {
        tone(csPin, csminusFreq, csminusDur);
      }

      digitalWrite(ledPin, HIGH);

      // Print trial start time
      if (csplus_trials[nextTrial]) {
        Serial.print(code_trial_onset_csplus);
      }
      else {
        Serial.print(code_trial_onset_csminus);
      }
      Serial.print(DELIM);
      Serial.println(ts);
    }

    // End of trial
    // Ends on either time limit.
    else if (inTrial && 
             ts >= (trials[nextTrial] + trialDur)) {
      inTrial = false;
      endOfRail = false;
      resetConveyer = true;

      digitalWrite(ledPin, LOW);
      
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
  
  // -- 2. TRACK MOVEMENT -- //
  if (inTrial &&
      !endOfRail &&
      digitalRead(railStopPin)) {
    // End of track reached
    endOfRail = true;

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

      if (inTrial &&
          csplus_trials[nextTrial] &&
          trackOutVal > 0 &&
          !endOfRail) {
        
        byte steps2take = trackOutVal >> STEPSCALE;
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
  static unsigned long nextResetTS;
  
  if (resetConveyer) {
    // Stop when start of rail reached
    if (digitalRead(railStartPin)) {
      resetConveyer = false;
    }
    else {
      if (ts >= nextResetTS) {
        Serial1.write((byte)STEPCODE);
        Serial1.write((byte)0);
        Serial1.write((byte)0);  // This value doesn't really matter
        
        nextResetTS = ts + trackPeriod;
      }
    }
  }
}

