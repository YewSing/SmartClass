# Use Cases: Environmental Sensing & Automated Control

**Modules:** 3 (Environmental Sensing), 4 (Automated Environment Actuation)
**Owner:** Shino

---

## UC-09: Monitor Environmental Sensors

- **Actor:** System (primary)
- **Description:** Continuously reads temperature, LDR light, CO2, and occupancy data from classroom sensors and transmits readings to the ambient control module at regular intervals.
- **Preconditions:** At least temperature sensor and occupancy cameras operational; ambient control module reachable; system powered.
- **Postconditions:** Latest sensor readings stored and accessible; corresponding actuation UCs invoked if thresholds met; readings reflected on dashboard (FR-050).

**Main Flow:**
1. Read temperature from sensor at each polling interval (FR-014).
2. Derive occupancy count from ceiling cameras (FR-015).
3. Read ambient light intensity from LDR sensor (FR-016).
4. Read CO2 concentration from CO2 sensor (FR-017).
5. Timestamp all readings; transmit to ambient control module within 5 seconds (NFR-29).
6. Evaluate each reading against configured thresholds.
7. Temperature threshold breached → invoke UC-10 (FR-018).
8. Zero occupancy sustained beyond configured duration → invoke UC-12 (FR-019).
9. Light intensity out of range → invoke UC-11 (FR-021).
10. Transmit all readings to lecturer dashboard (FR-050, NFR-27).

**Exception Flows:**
- *Sensor read failure:* Log failure; raise sensor fault alert on dashboard (FR-051); continue polling remaining sensors.
- *Ambient control module unreachable:* Buffer readings locally; retry on reconnect (NFR-21); raise connectivity alert.

---

## UC-10: Auto-adjust Air Conditioning

- **Actor:** System (primary)
- **Description:** Automatically issues a command to adjust the classroom AC when temperature breaches the configured threshold and occupancy meets the minimum required for AC activation.
- **Preconditions:** UC-09 delivered a temperature reading breaching threshold (FR-018); occupancy count meets minimum threshold for required continuous duration (FR-023); AC unit connected; no manual override active (UC-13).
- **Postconditions:** Actuation command sent to AC unit (FR-018); delivered and acknowledged within 2 seconds (NFR-20); dashboard reflects updated AC status.

**Main Flow:**
1. Receive temperature reading and occupancy count from UC-09.
2. Confirm occupancy has met or exceeded threshold for required continuous duration (FR-023).
3. Determine required AC adjustment based on temperature vs. configured range (FR-018).
4. Send actuation command to AC controller.
5. Receive acknowledgement within 2 seconds (NFR-20).
6. Update environmental status on dashboard.

**Alternative Flows:**
- *Occupancy below threshold:* Do not activate AC (FR-023); re-evaluate at next polling cycle.

**Exception Flows:**
- *AC controller unresponsive:* Retry up to 3 times; if all fail, raise actuation failure alert (FR-051).

---

## UC-11: Auto-control Lighting

- **Actor:** System (primary)
- **Description:** Automatically adjusts classroom lighting based on LDR readings falling outside the acceptable range, or when occupancy is first detected after the room was empty.
- **Preconditions:** UC-09 delivered an LDR reading or occupancy event; lighting control interface connected; no manual override active (UC-13).
- **Postconditions:** Lighting actuation command issued and acknowledged within 2 seconds (NFR-20); dashboard reflects updated lighting status.

**Main Flow:**
1. Receive trigger from UC-09: LDR reading breach (FR-021) or occupancy-detected event after empty room (FR-022).
2. For LDR trigger: determine required lighting adjustment (increase or decrease).
3. For occupancy trigger: issue immediate command to turn on lights (FR-022).
4. Send lighting actuation command to lighting controller.
5. Receive acknowledgement within 2 seconds (NFR-20).
6. Update environmental status on dashboard.

**Alternative Flows:**
- *Lights already at target state:* Skip actuation command.

**Exception Flows:**
- *Lighting controller unresponsive:* Retry command; raise actuation failure alert if retries fail (FR-051).

---

## UC-12: Auto-shutoff Appliances When Room Empty

- **Actor:** System (primary)
- **Description:** When the classroom has been empty for longer than the configured duration, automatically turns off all electrical appliances to conserve energy.
- **Preconditions:** UC-09 reported zero occupancy sustained for at least the configured empty-room duration (FR-019); appliance controls connected; no manual override active (UC-13).
- **Postconditions:** All configured appliances commanded off (FR-019); all commands acknowledged within 2 seconds (NFR-20); dashboard reflects updated states.

**Main Flow:**
1. UC-09 confirms zero occupancy sustained for configured duration (FR-019).
2. Compile list of appliances to shut off (lights, AC, projectors).
3. Send shutoff command to each appliance controller sequentially.
4. Each controller acknowledges within 2 seconds (NFR-20).
5. Log shutoff event with timestamp.
6. Update environmental status panel on dashboard.

**Alternative Flows:**
- *Occupancy detected before shutoff completes:* Abort remaining commands; invoke UC-11 to restore lighting (FR-022).

**Exception Flows:**
- *One or more controllers unresponsive:* Retry; raise actuation failure alert if retries fail (FR-051); continue issuing commands to remaining responsive appliances.

---

## UC-13: Manually Override Environmental Controls

- **Actor:** Lecturer / Admin
- **Description:** Manually overrides automated environmental control settings (AC or lights), bypassing sensor-driven actuation logic temporarily.
- **Preconditions:** Actor authenticated with Lecturer or Admin role (NFR-03, NFR-04); target appliance control interface accessible.
- **Postconditions:** Selected appliance set to actor-chosen state (FR-020); override state logged and visible on dashboard; automated actuation for overridden appliance suspended until released.

**Main Flow:**
1. Actor navigates to environmental controls section on dashboard.
2. Actor selects target appliance and desired manual state (FR-020).
3. System sends manual actuation command to appliance controller.
4. Controller acknowledges within 2 seconds (NFR-20).
5. System records override event; displays active override indicator on dashboard.
6. Automated actuation rules for the appliance suspended for duration of override.

**Alternative Flows:**
- *Actor releases override:* System re-enables automated actuation; immediately re-evaluates current sensor readings and issues commands if needed.

**Exception Flows:**
- *Appliance controller unresponsive:* Notify actor; prompt retry.
