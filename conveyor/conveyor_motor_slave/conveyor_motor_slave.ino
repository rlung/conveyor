/* 
conveyor_motor_slave

For use with the Adafruit Motor Shield v2 
---->  http://www.adafruit.com/products/1438
*/


#include <Wire.h>
#include <Adafruit_MotorShield.h>

// Create the motor shield object with the default I2C address
Adafruit_MotorShield AFMS = Adafruit_MotorShield();

// Set stepper motor with 200 steps per revolution to motor port #2 (M3 and M4)
Adafruit_StepperMotor *myMotor = AFMS.getStepper(200, 2);


void setup() {
  Serial.begin(9600);
  AFMS.begin();
  myMotor -> setSpeed(50);
  Serial.println("Motor slave\nTell me what to do:");
  Serial.println("  0: stop");
  Serial.println("  1: move forward");
  Serial.println("  2: move backward");
}


void loop() {
  static int move;

  if (Serial.available()) {
    byte input = Serial.read();
    if (input == '1') move = 1;
    else if (input == '0') move = 0;
    else if (input == '2') move = -1;
  }

  if (move) {
    if (move < 0 ) myMotor -> step(5, FORWARD, DOUBLE);
    else if (move > 0) myMotor -> step(5, BACKWARD, DOUBLE);
  }
}
