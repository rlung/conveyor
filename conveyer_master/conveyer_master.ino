// conveyer_track_rotary
// Moves track according to rotary encoder.
// Pin Z is not used (if it exists).


#include <Stepper.h>


// Pins
const int pinA = 2;
const int pinB = 3;

//
volatile int trackChange = 0;   // Rotations within tracking epochs

const int stepsPerRot = 200;  // change this to fit the number of steps per revolution
Stepper myStepper(stepsPerRot, 8, 9, 10, 11);



void track() {
  // Track changes in rotary encoder via interrupt
  if (digitalRead(pinB)) trackChange++;
  else trackChange--;
}

// SETUP code ////////////////
void setup() {
  pinMode(pinA, INPUT);
  pinMode(pinB, INPUT);
  attachInterrupt(digitalPinToInterrupt(pinA), track, RISING);

  Serial.begin(9600);
}

// LOOP code ////////////////
void loop() {
  static const unsigned long start = millis();
  
  static int trackts;
  static int lastts;
  static const int trackPeriod = 50;
  static unsigned long nextTrackTS = trackPeriod;
  static const int tracksPerMin = 60000 / trackPeriod;
  static int trackOutVal = 0;
  static const int k = -10;   // Dividing factor for distance from tracking to steps on motor
  
  static unsigned long trialts;
  static unsigned long lastTrialts;
  static const unsigned long trialDur = 60000;
  static const int railSteps = 250;  // Number of steps across entire rail

  unsigned long ts = millis() - start;

  // -- 0. TRACK MOVEMENT -- //
  trackts = ts % trackPeriod;
  if (trackts < lastts) {
    Serial.print("Track: ");
    Serial.print(trackChange);
    int trackOutVal = trackChange;
    trackChange = 0;
    
    if (trackOutVal) {
      // The number of steps on the motor is proportional to the distance moved
      // from tracking. The speed is set so that the number of steps will take the
      // amount of time between each read of track value (ie, trackPeriod)
  
      // Set parameters
      int steps2take = trackOutVal / k;
      unsigned long stepSpeed = (unsigned long)abs(steps2take) * stepsPerRot * tracksPerMin / 100000;
//      unsigned long stepSpeed = abs(steps2take) * stepsPerRot * tracksPerMin;
      Serial.print(" | Speed: ");
      Serial.print(stepSpeed);
      myStepper.setSpeed(stepSpeed);
  
      // Step
      myStepper.step(steps2take);
  
      Serial.print(" | Step: ");
      Serial.println(steps2take);
    }
    else Serial.println("");
  }

  lastts = trackts;

  // -- 1. RESET CONVEYER POSITION -- //
  // trialts = ts - lastTrialts;
  // if (trialts >= trialDur) {
  //   myStepper.setSpeed(60);
  //   myStepper.step(-railSteps);
  //   lastTrialts = ts;
  // }
}
