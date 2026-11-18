<div class="cover">RA-3 Six-Axis Articulated Robot</div>
<div class="cover-sub">Operating and Service Manual</div>
<div class="cover-sub">Document RA3-SM-EN, Revision 1.0, November 2026</div>
<div class="cover-sub">Fabrikon Automation (fictional manufacturer)</div>

This is a synthetic manual written for the Maintenance Copilot project. The RA-3 robot and its manufacturer do not exist. All values are invented and must not be used to service real equipment. Licensed under CC BY 4.0.

<!-- pagebreak -->

# 1 About this manual

## 1.1 Scope

This manual covers installation, operation, condition monitoring, troubleshooting and preventive maintenance of the RA-3 six-axis articulated robot with controller RC-30 and condition monitoring module CMM-3. It applies to robots with serial numbers RA3-24-0001 and higher and to controller firmware 4.2 and higher.

The manual is written for trained maintenance technicians. Operators who only start and stop the robot should use the short-form operating guide RA3-OG-EN instead.

## 1.2 Revision history

| Revision | Date | Change |
|---|---|---|
| 0.9 | 2026-09 | Pre-release for pilot plants |
| 1.0 | 2026-11 | First release. Added CMM-3 alarm limits (section 4.4), troubleshooting per fault mode (chapter 7), torque table (section 9.1) |

## 1.3 Conventions

Section references are written as "see section 7.3". Error codes are written as E-nnn for alarms that stop the robot and W-nnn for warnings that only log an event. Joint numbers run from J1 (base rotation) to J6 (tool flange rotation).

Values in this manual use SI units. Torque values are given in newton metres (Nm), temperatures in degrees Celsius (°C), vibration as RMS acceleration in multiples of standard gravity (g) and motor current as RMS current in amperes (A).

## 1.4 Related documents

| Document | Number | Content |
|---|---|---|
| Short-form operating guide | RA3-OG-EN | Start, stop, jog, teach pendant basics |
| Controller manual | RC30-SM-EN | RC-30 cabinet, drives, I/O, fieldbus |
| Spare parts catalogue | RA3-SP-EN | Exploded views and part numbers |
| Safety manual | RA3-SAF-EN | Risk assessment, safety functions, validation |

<!-- pagebreak -->

# 2 Safety

## 2.1 Signal words

**DANGER** indicates a hazardous situation that will cause death or serious injury if not avoided.

**WARNING** indicates a hazardous situation that could cause death or serious injury if not avoided.

**CAUTION** indicates a hazardous situation that could cause minor or moderate injury.

**NOTICE** indicates a situation that could damage the robot or the workpiece but does not put persons at risk.

## 2.2 Lockout and tagout

**DANGER** Never enter the robot cell while the controller is in automatic mode. Before any work inside the safety fence:

1. Stop the program and switch the mode selector on the teach pendant to T1.
2. Move the robot to the service position (all joints at 0°, J5 at -90°) if it can still be moved safely.
3. Switch off the main switch on the RC-30 cabinet and secure it with your personal padlock.
4. Wait at least 5 minutes for the DC link capacitors to discharge. Check that the DC link LED on each drive is off.
5. Verify zero energy by trying to release the brakes from the pendant. The pendant must show "No drive power".

Each technician working in the cell attaches their own lock. The cell is only re-energised when every lock has been removed by its owner.

## 2.3 Hot surfaces

**CAUTION** Motor housings and the J3 gearbox can reach 90 °C during a thermal fault (see section 7.2). Let the robot cool down for at least 30 minutes after a thermal alarm before touching the J3 housing, or wear heat-resistant gloves.

## 2.4 Stored mechanical energy

**WARNING** Joints J2 and J3 are held by spring-applied brakes. When a brake is released manually, the arm falls under gravity. Support the arm with a crane or the support bracket RA3-T-110 before releasing a brake or removing a motor from J2 or J3.

The J2 axis has a gas-spring counterbalance charged to 120 bar. Do not open or remove the counterbalance cylinder. Replacement is a factory service operation.

## 2.5 Personal protective equipment

Wear safety shoes, safety glasses and cut-resistant gloves for all mechanical work. Wear nitrile gloves when handling gear grease. Use hearing protection when running vibration tests at full speed.

<!-- pagebreak -->

# 3 System overview

## 3.1 Main components

The RA-3 system consists of the manipulator (the arm), the RC-30 controller cabinet, the teach pendant TP-3 and the condition monitoring module CMM-3. The CMM-3 is mounted in the RC-30 cabinet and reads three additional sensors on the arm.

| Component | Type | Function |
|---|---|---|
| Manipulator | RA-3 | Six-axis arm, payload 12 kg, reach 1,420 mm |
| Controller | RC-30 | Motion control, six servo drives, safety controller |
| Teach pendant | TP-3 | Jogging, programming, alarm display and reset |
| Condition monitoring module | CMM-3 | Records temperature, vibration and motor current, detects deviations, forwards alarms to the plant network |
| Gearboxes J1 to J3 | Cycloidal, ratio 121:1 to 153:1 | Low-backlash high-torque reduction |
| Gearboxes J4 to J6 | Harmonic drive with toothed belt stage | Compact wrist reduction |

## 3.2 Joint designation

| Joint | Motion | Range | Max. speed |
|---|---|---|---|
| J1 | Base rotation | ±170° | 220 °/s |
| J2 | Lower arm (shoulder) | -90° to +135° | 200 °/s |
| J3 | Upper arm (elbow) | -160° to +70° | 230 °/s |
| J4 | Forearm rotation | ±190° | 380 °/s |
| J5 | Wrist bend | ±125° | 380 °/s |
| J6 | Tool flange rotation | ±360° | 550 °/s |

## 3.3 Condition monitoring sensors

The CMM-3 reads three sensors on the arm once per second. Each reading is published on the plant MQTT broker under the topic factory/robot/(arm id)/(sensor), for example factory/robot/arm_02/vibration. In a standard three-robot cell the arms are named arm_01, arm_02 and arm_03 from the cell entrance.

| Sensor | Measured at | Unit | Principle |
|---|---|---|---|
| temperature | J3 gearbox housing, next to the motor flange | °C | PT100 surface sensor |
| vibration | J2 motor flange, radial direction | g (RMS) | MEMS accelerometer, 10 Hz to 1 kHz band |
| current | J2 servo motor phase current | A (RMS) | Hall-effect sensor in the RC-30 drive |

J2 and J3 carry the highest static load, so they are the first joints to show gearbox, bearing and drive problems. A fault elsewhere in the arm usually shows up in at least one of these three signals.

## 3.4 How the CMM-3 detects deviations

The CMM-3 learns a baseline (mean and standard deviation) for each sensor during the first 8 hours of normal production after commissioning. After that, every reading is converted into a z-score: the distance from the baseline mean in standard deviations. A reading with an absolute z-score above 3 is flagged as an anomaly and appears in the anomaly log with the time, arm, sensor, value and z-score.

Independently of the z-score, the CMM-3 compares each reading with the fixed warning and alarm limits in section 4.4. Fixed limits raise W-codes and E-codes. Z-score anomalies are logged only and do not stop the robot.

**NOTICE** A z-score anomaly without a fixed-limit warning is an early sign, not a fault. Check the trend before acting. Several anomalies on the same sensor within 15 minutes justify an inspection.

<!-- pagebreak -->

# 4 Technical specifications

## 4.1 General data

| Parameter | Value |
|---|---|
| Number of axes | 6 |
| Rated payload | 12 kg |
| Maximum reach | 1,420 mm |
| Position repeatability (ISO 9283) | ±0.03 mm |
| Weight of manipulator | 168 kg |
| Mounting | Floor, ceiling or wall (wall mounting limits J1 range to ±60°) |
| Protection class | IP54 arm, IP67 wrist |
| Ambient temperature, operation | +5 °C to +40 °C |
| Ambient temperature, storage | -10 °C to +55 °C |
| Relative humidity | max. 85 %, non-condensing |
| Sound pressure level | below 70 dB(A) at 1 m |
| Supply voltage (RC-30) | 3 × 400 V AC ±10 %, 50/60 Hz |
| Rated power | 3.2 kVA |

## 4.2 Axis loads and moments

| Joint | Max. static torque | Max. dynamic torque | Allowed wrist moment |
|---|---|---|---|
| J1 | 880 Nm | 1,450 Nm | not applicable |
| J2 | 1,120 Nm | 1,900 Nm | not applicable |
| J3 | 520 Nm | 890 Nm | not applicable |
| J4 | 38 Nm | 62 Nm | 38 Nm |
| J5 | 38 Nm | 62 Nm | 38 Nm |
| J6 | 19 Nm | 31 Nm | 19 Nm |

## 4.3 Payload diagram

The rated payload of 12 kg applies to a centre of gravity up to 150 mm from the tool flange along the J6 axis and 100 mm off-axis. For a centre of gravity further away, reduce the payload linearly to 6 kg at 300 mm. A payload outside the diagram increases J2 motor current and shortens gearbox life. Enter the actual payload data in the controller (menu Setup > Payload) after every tool change; wrong payload data is a common cause of overcurrent alarms (see section 7.4).

## 4.4 Condition monitoring limits

The table lists the normal operating band and the fixed limits used by the CMM-3. The baseline values are typical for a robot running a standard pick-and-place cycle at 20 °C ambient temperature.

| Sensor | Typical baseline | Normal band | Warning limit | Alarm limit | Trip limit |
|---|---|---|---|---|---|
| temperature (J3 gearbox) | 62.5 °C | 55 to 70 °C | 75 °C (W-110) | 85 °C (E-112) | 95 °C (E-115) |
| vibration (J2 radial) | 1.55 g | 1.4 to 1.7 g | 3.0 g (W-210) | 5.0 g (E-217) | 8.0 g (E-219) |
| current (J2 motor) | 6.0 A | 5.5 to 6.5 A | 9.0 A (W-310) | 10.0 A (E-312) | 14.0 A (E-315) |

The normal sensor noise is about ±1.0 °C for temperature, ±0.05 g for vibration and ±0.15 A for current (one standard deviation). An alarm limit stops the robot at the end of the current motion (controlled stop). A trip limit switches off drive power immediately (stop category 0).

<!-- pagebreak -->

# 5 Installation and commissioning

## 5.1 Foundation and anchoring

Mount the robot on a concrete floor of at least 200 mm thickness, quality C25/30 or better, or on a steel base plate of at least 30 mm thickness. Use the four anchor bolts M20 supplied with the robot. Tighten the anchor bolts to the torque in section 9.1 and re-check them after the first 100 operating hours. Loose anchor bolts are a frequent cause of vibration alarms on J2 (see section 7.3).

## 5.2 Cable connections

Connect the motor cable X1, the encoder cable X2 and the CMM-3 sensor cable X3 between the robot base and the RC-30 cabinet. Route the cables in the cable duct, separated from welding and mains cables by at least 200 mm. Do not bend the motor cable below a radius of 150 mm.

**NOTICE** A damaged or pinched X1 motor cable can cause intermittent overcurrent alarms on J2 (E-312) and drive ground faults (E-321).

## 5.3 First start-up

1. Check that all transport locks (red brackets on J2 and J3) have been removed.
2. Switch on the RC-30. The pendant shows the boot screen and then "Drives ready".
3. Jog every joint in T1 at 10 % speed over its full range. Listen for unusual noise.
4. Calibrate the payload (menu Setup > Payload > Identify).
5. Run the commissioning test program CMM_BASELINE for 8 hours of production-like motion so that the CMM-3 learns the sensor baselines (see section 3.4).
6. Record the learned baselines in the commissioning report. They are the reference for all later troubleshooting.

<!-- pagebreak -->

# 6 Alarms and error codes

## 6.1 Code structure

Every alarm has a letter and a three-digit number. The letter shows the severity: W for a warning (logged, robot continues) and E for an error (robot stops). The first digit shows the subsystem.

| First digit | Subsystem |
|---|---|
| 1 | Thermal (temperature sensor, motor and gearbox temperature) |
| 2 | Vibration and mechanics |
| 3 | Drive, motor current and power electronics |
| 4 | Communication (fieldbus, encoder, CMM-3 link) |
| 5 | Safety functions |

## 6.2 Error code list

| Code | Message | Meaning | First action |
|---|---|---|---|
| W-110 | J3 temperature high | J3 gearbox temperature above 75 °C | Check trend; see section 7.2 |
| E-112 | J3 overtemperature | J3 gearbox temperature above 85 °C, controlled stop | Let cool down; see section 7.2 |
| E-115 | J3 temperature trip | J3 gearbox temperature above 95 °C, drive power off | Do not restart before inspection; see section 7.2 |
| E-118 | Temperature sensor fault | PT100 open circuit or short circuit, reading outside -20 to 150 °C | Check sensor cable X3 and connector at J3 |
| W-120 | Cabinet temperature high | RC-30 cabinet interior above 45 °C | Clean cabinet filter mats; check cabinet fan |
| W-210 | J2 vibration high | J2 vibration RMS above 3.0 g | Check trend; see section 7.3 |
| E-217 | J2 vibration alarm | J2 vibration RMS above 5.0 g, controlled stop | See section 7.3 |
| E-219 | J2 vibration trip | J2 vibration RMS above 8.0 g, drive power off | Do not restart; inspect J2 and the tool; see section 7.3 |
| E-221 | Accelerometer fault | No signal or constant signal from the J2 accelerometer | Check sensor cable X3; replace sensor |
| W-230 | Collision detected | Torque deviation above the collision threshold on any joint | Inspect tool and fixture; check payload data |
| W-310 | J2 current high | J2 motor current above 9.0 A | Check payload data and trend; see section 7.4 |
| E-312 | J2 overcurrent | J2 motor current above 10.0 A, controlled stop | See section 7.4 |
| E-315 | J2 current trip | J2 motor current above 14.0 A, drive power off | Do not restart before checking for binding; see section 7.4 |
| E-321 | Drive ground fault | Leakage current from a motor phase to ground | Measure motor cable insulation; see section 7.4.4 |
| E-330 | DC link overvoltage | DC link voltage above 820 V during braking | Check braking resistor and its fuse |
| E-335 | Brake not released | Brake feedback shows a closed brake while the axis moves | Check brake voltage 24 V at the motor; see section 7.4 |
| E-401 | Encoder communication lost | No data from an absolute encoder | Check encoder cable X2; check encoder battery |
| E-405 | Encoder battery low | Encoder backup battery below 3.0 V | Replace battery with power on; see section 8.5 |
| W-420 | CMM-3 link lost | No sensor data from the CMM-3 for more than 10 s | Check CMM-3 status LED and network cable |
| E-501 | Emergency stop | An emergency stop button was pressed | Find the cause, release the button, reset |
| E-505 | Safety fence open | Fence door opened in automatic mode | Close the door, reset, restart program |
| E-510 | Safe speed exceeded | TCP speed above 250 mm/s in T1 | Reduce jog speed; check safety configuration |

## 6.3 Resetting an alarm

1. Read the full alarm text and the alarm history on the pendant (menu Diagnosis > Alarm log). Note the time, the code and the joint.
2. Remove the cause of the alarm. For E-1xx, E-2xx and E-3xx codes, follow the procedure in chapter 7.
3. Press RESET on the pendant. E-codes can only be reset in T1 mode.
4. Run the program in T1 at reduced speed for one cycle before returning to automatic mode.

**WARNING** Do not reset a trip alarm (E-115, E-219, E-315) repeatedly to keep production running. A second trip within 24 hours requires a full inspection of the affected joint.

<!-- pagebreak -->

# 7 Troubleshooting

## 7.1 General approach

Start every diagnosis from the data before opening the robot. Look at the last 15 minutes of all three CMM-3 signals for the alarming arm, not only the signal that raised the alarm. The shape of the signal over time narrows down the cause more than its peak value.

| Signal pattern | Typical fault mode | Section |
|---|---|---|
| Temperature rises slowly and steadily over many minutes; vibration and current stay normal | Thermal drift | 7.2 |
| Vibration jumps up and down in repeated bursts; temperature and current stay normal | Vibration spike | 7.3 |
| Current steps up within seconds and then stays high; temperature and vibration stay normal at first | Overcurrent | 7.4 |
| Two or more signals rise together | Combined mechanical fault, often a failing J2 or J3 bearing | 7.5 |
| A signal drops to zero or freezes at one value | Sensor or communication fault | 7.6 |

Compare the robot with its neighbours in the cell. If all arms show the same temperature rise, the cause is usually ambient (cell temperature, cooling air) rather than the robot.

## 7.2 Thermal drift (J3 temperature)

### 7.2.1 Symptoms

The J3 gearbox temperature rises gradually, typically by 20 to 30 °C over 20 to 60 minutes, while vibration and current stay inside their normal bands. The CMM-3 first logs z-score anomalies on the temperature sensor, then raises W-110 at 75 °C and E-112 at 85 °C. The rise is smooth and nearly linear; there are no sudden jumps.

### 7.2.2 Likely causes

| Rank | Cause | How to confirm |
|---|---|---|
| 1 | Lubricant degraded or insufficient in the J3 gearbox | Grease is dark, thin or smells burnt; last grease change overdue (see section 8.1) |
| 2 | J3 motor fan blocked or filter clogged | Fan does not turn or airflow is weak; dust on the fan guard |
| 3 | Duty cycle too high for the payload | J3 runs at high speed with full payload for long periods; cycle time was shortened recently |
| 4 | J3 brake dragging | Brake does not release fully; temperature rises even at low speed; often with W-310 on J3 |
| 5 | High ambient temperature in the cell | All robots in the cell are warmer than usual; cell above 35 °C |

### 7.2.3 Procedure

1. Check whether the neighbouring arms show the same rise. If yes, check the cell ventilation first.
2. Reduce the program speed override to 50 % and observe the trend for 10 minutes. A thermal drift caused by load or lubrication flattens at reduced speed; a dragging brake does not.
3. Stop the robot and lock out (see section 2.2). Let J3 cool down to below 45 °C.
4. Check the J3 motor fan and its filter. Clean the filter with compressed air from the inside out. Replace the fan if it does not turn freely.
5. Take a grease sample from the J3 drain plug. If the grease is dark, contains metal particles or is thinner than new grease, replace the grease (see section 8.2).
6. Measure the brake air gap on J3. The gap must be 0.2 to 0.4 mm.
7. Restart and run the CMM_BASELINE program for 60 minutes. The temperature must settle below 70 °C.

**NOTICE** Running repeatedly into E-112 shortens the lubricant life sharply. Every hour above 85 °C counts as 20 hours of normal operation for the grease change interval.

## 7.3 Vibration spike (J2 vibration)

### 7.3.1 Symptoms

The J2 vibration signal jumps repeatedly between its normal level of about 1.5 g and peaks of 5 to 10 g. The bursts often repeat at the same position in the program cycle. Temperature and motor current stay normal. The CMM-3 logs z-score anomalies on vibration first, then raises W-210 at 3.0 g, E-217 at 5.0 g and E-219 at 8.0 g.

### 7.3.2 Likely causes

| Rank | Cause | How to confirm |
|---|---|---|
| 1 | Loose J2 motor mounting bolts or loose J2 output flange bolts | Witness marks on bolt heads are offset; bolts turn below the torque in section 9.1 |
| 2 | Loose or unbalanced tool on the J6 flange | Tool moves by hand; vibration peaks at high J6 speed |
| 3 | Loose robot base anchor bolts | Base moves relative to the floor; vibration also felt on the base |
| 4 | Worn J2 main bearing | Rumbling noise when jogging J2 slowly; vibration rises over weeks, not minutes |
| 5 | Resonance at a programmed speed | Peak always at the same TCP speed; disappears when that speed is changed by 10 % |

### 7.3.3 Procedure

1. Find the program position where the bursts occur. Use the pendant trend view with the program line overlay.
2. Stop the robot and lock out (see section 2.2).
3. Check the tool on the J6 flange. Re-tighten the tool bolts to the torque in section 9.1.
4. Check the witness marks on the J2 motor mounting bolts and the J2 output flange bolts. Re-tighten all bolts of a joint to the torque in section 9.1 in a cross pattern if any mark is offset.
5. Check the base anchor bolts M20.
6. Jog J2 slowly in T1 over its full range and listen for rumbling or clicking. Rumbling points to a worn main bearing; contact service for a J2 bearing replacement.
7. If no mechanical cause is found, change the programmed speed in the affected segment by 10 % and check whether the bursts disappear (resonance).
8. Restart, run 30 minutes and confirm the vibration stays below 2.0 g.

**WARNING** Do not continue production with a vibration level above 5.0 g. A loose flange can shear the remaining bolts and drop the upper arm.

## 7.4 Overcurrent (J2 motor current)

### 7.4.1 Symptoms

The J2 motor current rises from about 6 A to 10 to 12 A within a few seconds and then stays at the higher level. It does not ramp slowly like a thermal drift and does not oscillate like a vibration spike. Temperature and vibration are normal at first; the motor temperature follows minutes later if the robot keeps running. The CMM-3 raises W-310 at 9.0 A, E-312 at 10.0 A and E-315 at 14.0 A.

### 7.4.2 Likely causes

| Rank | Cause | How to confirm |
|---|---|---|
| 1 | Payload heavier than configured, or wrong payload data after a tool change | Payload data in Setup > Payload does not match the actual tool and part |
| 2 | Mechanical binding in J2: collision damage, foreign object, damaged cable guide | J2 is hard to move with brakes released (two persons, arm supported) |
| 3 | J2 brake not releasing fully | E-335 in the alarm log; clicking or grinding at motion start |
| 4 | Damaged motor cable X1 or partial winding short | Insulation resistance below 10 MΩ; E-321 in the alarm log |
| 5 | Cold start with cold grease below +10 °C ambient | High current only in the first 15 minutes after start; disappears when warm |

### 7.4.3 Procedure

1. Check the alarm log for E-335, E-321 and W-230 around the time of the current step.
2. Compare the payload data in Setup > Payload with the actual tool and part. Run Setup > Payload > Identify if in doubt.
3. Stop the robot and lock out (see section 2.2). Support the arm with the support bracket RA3-T-110.
4. Inspect J2 for collision damage, trapped objects and damage to the cable guide.
5. Release the J2 brake manually with the brake release box RA3-T-120 and move the arm by hand. It must move evenly without hard spots.
6. Measure the brake air gap on J2 (0.2 to 0.4 mm) and the brake supply voltage (24 V ±10 %).
7. Restart and run 30 minutes at 100 % override. The current must stay below 7.0 A in the standard cycle.

### 7.4.4 Insulation measurement on the motor cable

Disconnect X1 at both ends. Measure the insulation resistance between each phase and ground with 500 V DC. The value must be at least 10 MΩ for the cable and at least 5 MΩ for the motor winding. Replace the cable if any value is lower.

**DANGER** Insulation testers produce high voltage. Disconnect the drive before testing; the drive electronics are destroyed by the test voltage.

## 7.5 Combined symptoms

When temperature, vibration and current rise together, the cause is usually a failing bearing or a damaged gearbox in J2 or J3. Friction raises the current, the damaged rolling elements raise the vibration and the friction heat raises the temperature. Stop the robot, lock out and contact service. Do not try to clear the alarms by greasing; fresh grease can mask the symptoms for a few days while the damage continues.

## 7.6 Sensor and communication faults

A signal that suddenly drops to zero, jumps to the end of its range or stays at exactly the same value for more than 60 seconds is almost always a sensor or wiring problem, not a machine problem. Check the CMM-3 status LED (green: running, flashing red: sensor fault), the X3 sensor cable and the connector at the sensor. The CMM-3 raises E-118 for the temperature sensor, E-221 for the accelerometer and W-420 when the whole module is offline.

<!-- pagebreak -->

# 8 Preventive maintenance

## 8.1 Maintenance intervals

Intervals are given in operating hours as shown on the pendant (menu Diagnosis > Counters). Whichever comes first, operating hours or calendar time, applies. Shorten all intervals by half for operation above 35 °C ambient or in dusty environments.

| Interval | Task | Section |
|---|---|---|
| Daily | Visual check of cables, tool and fence; check pendant for warnings | 8.3 |
| 500 h or 3 months | Clean J3 motor fan filter; check CMM-3 trends for slow changes | 8.3 |
| 2,000 h or 6 months | Check witness marks on J2 and J3 bolts; check base anchor bolts | 9.1 |
| 5,000 h or 1 year | Inspect and re-tension J5/J6 toothed belts; measure brake air gaps J2 and J3 | 8.4 |
| 10,000 h or 2 years | Replace grease in J1, J2 and J3 gearboxes; replace encoder battery | 8.2, 8.5 |
| 20,000 h or 4 years | Replace J4 to J6 harmonic drive grease; replace motor cable X1 if flexing wear is visible | 8.2 |
| 40,000 h | General overhaul by Fabrikon service: bearings, seals, counterbalance | contact service |

## 8.2 Lubrication

Use only the synthetic gear grease RA-G2 (part number RA3-L-002). Do not mix with other greases; mixed greases can separate and lose their load capacity.

| Joint | Grease | Quantity | Fill port |
|---|---|---|---|
| J1 gearbox | RA-G2 | 920 g | Grease nipple on the base, drain plug opposite |
| J2 gearbox | RA-G2 | 780 g | Grease nipple on the left side of the shoulder |
| J3 gearbox | RA-G2 | 410 g | Grease nipple on the elbow, drain plug below |
| J4 to J6 harmonic drives | RA-G4 | 45 g each | Factory service only |

Grease change procedure for J1 to J3:

1. Run the robot for 20 minutes so the grease is warm and flows.
2. Lock out (see section 2.2). Move the joint so the drain plug points down if possible.
3. Remove the drain plug and the fill port cap. Let the old grease drain for 10 minutes.
4. Pump new grease through the grease nipple until clean grease comes out at the drain port. Do not exceed the quantity in the table by more than 10 %.
5. Jog the joint over its full range twice with the drain open so excess grease can escape.
6. Fit the drain plug with a new seal ring and tighten it to the torque in section 9.1.

**NOTICE** Too much grease raises the gearbox pressure and temperature and can push the grease past the shaft seal. A J3 temperature rise right after a grease change usually means overfilling.

## 8.3 Routine inspection

Daily: check the arm for loose cables, oil or grease leaks and damage to the tool. Check the pendant for active warnings.

Every 500 hours: remove and clean the J3 motor fan filter. Open the CMM-3 trend view and compare the 7-day average of each signal with the commissioning baseline. A temperature average more than 5 °C above baseline, a vibration average more than 0.3 g above baseline or a current average more than 0.8 A above baseline justifies a planned inspection before an alarm occurs.

## 8.4 Toothed belts J5 and J6

Check the belt tension with the frequency meter RA3-T-130. The natural frequency must be 95 to 115 Hz for J5 and 130 to 150 Hz for J6. Re-tension the belt if the frequency is outside this range. Replace the belt if teeth are worn, cracked or missing.

## 8.5 Encoder battery

The absolute encoders keep their position with a 3.6 V lithium battery pack in the robot base. Replace the battery every 10,000 hours, or when E-405 appears. Replace the battery with the controller switched on; otherwise the encoders lose their position and every joint must be re-mastered.

<!-- pagebreak -->

# 9 Mechanical service

## 9.1 Tightening torques

Use a calibrated torque wrench. Tighten bolts of one joint in a cross pattern in two steps: first to 50 % of the value, then to 100 %. Apply thread locker RA3-L-010 (medium strength) to all bolts marked with an asterisk. Mark each tightened bolt with a witness line across the bolt head and the housing.

| Joint or part | Bolt | Property class | Quantity | Torque |
|---|---|---|---|---|
| Base anchor bolts | M20 | 8.8 | 4 | 390 Nm |
| J1 gearbox to base | M12 | 12.9 | 12 | 135 Nm |
| J2 motor mounting* | M8 | 12.9 | 4 | 40 Nm |
| J2 gearbox output flange* | M12 | 12.9 | 16 | 135 Nm |
| J3 motor mounting* | M8 | 12.9 | 4 | 40 Nm |
| J3 gearbox output flange* | M10 | 12.9 | 12 | 79 Nm |
| J4 housing cover | M6 | 8.8 | 8 | 10 Nm |
| J5/J6 belt tensioner | M6 | 8.8 | 2 per joint | 12 Nm |
| Tool flange (J6, ISO 9409-1-50-4-M6) | M6 | 12.9 | 4 | 16 Nm |
| Gearbox drain plugs J1 to J3 | M14 × 1.5 | steel with seal ring | 1 per joint | 25 Nm |

## 9.2 Replacing the J3 gearbox grease seal

1. Lock out (see section 2.2) and support the upper arm with the support bracket RA3-T-110.
2. Drain the J3 grease (see section 8.2).
3. Remove the J3 motor (four M8 bolts). Keep the motor shims together with the motor.
4. Pull the old seal with the seal puller RA3-T-140. Do not scratch the shaft.
5. Press in the new seal RA3-S-031 with the press tool until it sits flush with the housing.
6. Refit the motor with the original shims, tighten the bolts to the torque in section 9.1 and refill the grease.
7. Check the J3 temperature trend during the next 8 hours of production.

## 9.3 Replacing the J3 motor fan

1. Lock out (see section 2.2).
2. Unplug the fan connector at the J3 motor terminal box.
3. Remove the four M4 screws of the fan guard and lift off fan and guard together.
4. Fit the new fan RA3-E-044 with the airflow arrow pointing towards the motor.
5. Tighten the M4 screws to 2.5 Nm, plug in the connector and check that the fan runs when the drives are switched on.

## 9.4 Replacing the J2 accelerometer

1. Lock out (see section 2.2).
2. Unplug the sensor cable at the J2 motor flange.
3. Unscrew the sensor (M6 stud) and clean the mounting face.
4. Apply a thin film of coupling grease, screw in the new sensor RA3-E-052 and tighten to 8 Nm. A loose sensor measures wrong vibration values.
5. Restart and check that the CMM-3 shows about 1.5 g in the standard cycle.

<!-- pagebreak -->

# 10 Spare parts

| Part number | Description | Used in |
|---|---|---|
| RA3-L-002 | Gear grease RA-G2, 1 kg cartridge | Section 8.2 |
| RA3-L-010 | Thread locker, medium strength, 50 ml | Section 9.1 |
| RA3-S-031 | Shaft seal J3 gearbox | Section 9.2 |
| RA3-E-044 | Motor fan J3, 24 V DC | Section 9.3 |
| RA3-E-052 | Accelerometer J2, MEMS, M6 stud | Section 9.4 |
| RA3-E-060 | PT100 surface sensor J3 | Section 7.6 |
| RA3-E-071 | Encoder battery pack, 3.6 V lithium | Section 8.5 |
| RA3-C-101 | Motor cable X1, 7 m | Section 7.4.4 |
| RA3-M-210 | Toothed belt J5 | Section 8.4 |
| RA3-M-211 | Toothed belt J6 | Section 8.4 |
| RA3-T-110 | Support bracket for upper arm | Sections 2.4, 7.4, 9.2 |
| RA3-T-120 | Brake release box | Section 7.4 |
| RA3-T-130 | Belt frequency meter | Section 8.4 |
| RA3-T-140 | Seal puller | Section 9.2 |

<!-- pagebreak -->

# Appendix A Glossary

**Baseline**: mean and standard deviation of a sensor signal learned during commissioning (see section 3.4).

**Controlled stop**: the robot finishes the current motion and stops with drive power on (stop category 1).

**Harmonic drive**: compact strain-wave gear with very low backlash, used in the wrist joints J4 to J6.

**RMS**: root mean square, the effective value of an oscillating signal.

**TCP**: tool centre point, the reference point at the tip of the tool.

**Witness mark**: a paint line across a bolt head and the housing that shows at a glance whether the bolt has turned.

**Z-score**: the distance of a reading from the baseline mean, measured in standard deviations. An absolute z-score above 3 is logged as an anomaly.
