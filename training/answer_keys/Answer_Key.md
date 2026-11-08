# Answer key

_Generated 2026-11-08 20:00 UTC. For instructors and self-checking after the exercise. Ohmetry course material for engineering learning. It is not accredited training. Worked examples use preliminary assumptions, not manufacturer data. It does not replace the standards, manufacturer data or a qualified engineer._

## Exercises

### Module 01: Introduction to Data Centre Electrical Design

**1.1** Answer: **3,608 A**
Working: I = 2,500,000 / (sqrt3 x 400)

**1.2** Answer: **1,897 kVA**
Working: S = sqrt(1800^2 + 600^2)

### Module 02: IT Load, Facility Load and PUE

**2.1** Answer: **127.7 kW**
Working: P_loss = 2000 x (100/94 - 1)

**2.2** Answer: **1.3711 -**
Working: Re-run the load model with efficiency 94 %: the UPS loss rises and the distribution losses rise with it.

### Module 03: Electrical Architecture, A/B Paths and Redundancy

**3.1** Answer: **71.6 %**
Working: loading = load / (1 x 4000 x 1.0)

**3.2** Answer: **3,200 kVA**
Working: (3 - 1) x 2000 x 0.8

### Module 04: MV Distribution and Transformer Sizing

**4.1** Answer: **3,352 kVA**
Working: S = 2866 / (0.90 x 0.95)

**4.2** Answer: **65.6 kA**
Working: Z_T = K_T x 0.06 x 400^2 / 2.5e6; I = 1.05 x 400 / (sqrt3 x Z_T)

### Module 05: Generator Sizing and Transient Performance

**5.1** Answer: **1,600 kW**
Working: 2000 x 0.8

**5.2** Answer: **4 units**
Working: Needed running units = ceil(2687 / (1600 x 0.8)) = 3; add one spare for N+1.

### Module 06: UPS Architecture and Battery Sizing

**6.1** Answer: **360.0 kWh**
Working: E = 1800 x 12 / 60

**6.2** Answer: **542.8 kWh**
Working: E_nom = 360 / 0.96 / (0.8 x 0.95) x 1.1

### Module 07: LV Distribution and Switchgear Selection

**7.1** Answer: **4,596 A**
Working: I = 4136 / 0.9

**7.2** Answer: **FAIL **
Working: 65 < 74

### Module 08: Cable Sizing, Ampacity and Voltage Drop

**8.1** Answer: **0.1832 mohm/m**
Working: R = 0.017241 x (1 + 0.00393 x 70) / 120

**8.2** Answer: **0.5086 %**
Working: dV = sqrt3 x 300 x 40 x (0.00007 x 0.9 + 0.00008 x 0.4359); divide by 400

### Module 09: Short-Circuit Fundamentals and Protection Coordination

**9.1** Answer: **98.8 kA**
Working: kappa = 1.02 + 0.98 exp(-0.3); ip = kappa sqrt2 x 40

**9.2** Answer: **10.5 kA**
Working: Ik'' = S / (sqrt3 U) because Z = c U^2 / S

### Module 10: Earthing, Bonding, Lightning and Power Quality

**10.1** Answer: **0.9586 ohm**
Working: Rg = 100 [1/1200 + 1/sqrt(50000) (1 + 1/(1 + 0.5 sqrt(20/2500)))]

**10.2** Answer: **1 %**
Working: mean = 400; max deviation = 4; 4/400 = 1 %

### Module 11: Single-Line Diagrams, Schedules and Engineering Reports

**11.1** Answer: **NOT VERIFIED **
Working: A pass on unverified inputs is not evidence the design works.

**11.2** Answer: **WARNING **
Working: A preliminary exceedance is still reported.

### Module 12: Commissioning, FAT, SAT and Integrated Systems Testing

**12.1** Answer: **800.0 kW**
Working: 0.75 x 1600 - 400

**12.2** Answer: **225.0 kWh**
Working: E = 1500 x 9 / 60

## Question bank answers

| Id | Answer | Explanation |
|---|---|---|
| Q01.1 | B. The UPS bridges the time until generators accept load | The UPS and battery carry the load during the gap. |
| Q01.2 | B. The most onerous failure the design is required to survive | It is the most onerous failure the project has decided is credible. |
| Q01.3 | B. Transformer short-circuit impedance | Impedance comes from the test report. |
| Q01.4 | B. 500 kVA | sqrt(300^2 + 400^2) = 500. |
| Q02.1 | B. Reactive and real power are different quantities; apparent power is the vector sum | S = sqrt(P^2 + Q^2). |
| Q02.2 | B. Efficiency falls | Loss = P x (100/eta - 1). |
| Q02.3 | B. A power ratio at the design point | It is a ratio of power, not annual energy. |
| Q02.4 | B. Not possible: facility power cannot be below IT power | Facility power includes the IT load plus overhead. |
| Q03.1 | B. Two complete independent paths, each able to carry the whole load | Each path can carry the whole critical load. |
| Q03.2 | A. Load carried with the largest unit out | The load must be carried with one unit out. |
| Q03.3 | B. Not independent at that point | A shared point is a common failure. |
| Q03.4 | B. A double contingency, informational unless the project decides it is credible | It is beyond N+1. |
| Q04.1 | B. The derated continuous rating | Derating first. |
| Q04.2 | B. WARNING needing a decision | It needs a recorded decision. |
| Q04.3 | B. A higher fault level | Less impedance passes more fault current. |
| Q04.4 | B. Nothing in continuous sizing | It is not used for continuous loading. |
| Q05.1 | B. Different ISO 8528 rating bases | They are not interchangeable. |
| Q05.2 | B. 1,600 | kVA x pf. |
| Q05.3 | A. Steps cause frequency and voltage dips that depend on the unit | Needs manufacturer data. |
| Q05.4 | B. Not automatically good: minimum-load guidance applies | Light running has its own limits. |
| Q06.1 | B. The manufacturer's constant-power discharge data at end of life | Capacity depends on discharge rate. |
| Q06.2 | A. 333 kWh | 2000 x 10 / 60. |
| Q06.3 | B. kVA first | kVA = kW / 0.95 is larger. |
| Q06.4 | B. The whole critical load | That is the point of 2N. |
| Q07.1 | B. Design current divided by derating | I / k. |
| Q07.2 | B. The prospective fault level at the busbars | Including the peak current. |
| Q07.3 | B. The assembly manufacturer's verification | The designer checks the evidence. |
| Q07.4 | B. NOT VERIFIED | They are never assumed. |
| Q08.1 | B. Higher | Resistance rises with temperature. |
| Q08.2 | B. The standard for the installation method or the manufacturer | It depends on construction and layout. |
| Q08.3 | B. Divides between runs | Per-run share. |
| Q08.4 | B. Minimum conductor area for a fault of given duration | S >= I sqrt(t) / k. |
| Q09.1 | B. The utility's written statement | It is a site/utility input. |
| Q09.2 | A. X/R | kappa = 1.02 + 0.98 exp(-3 R/X). |
| Q09.3 | B. Device time-current curves and a study | Curves and a validated study. |
| Q09.4 | B. Only the transformer rating and impedance | It assumes an infinite source. |
| Q10.1 | A. Earth-fault current times grid resistance | GPR = Ig x Rg. |
| Q10.2 | C. A detailed mesh and step calculation may still be required | It is only a screening. |
| Q10.3 | B. A complete verified risk assessment and design | Not otherwise. |
| Q10.4 | B. 1 % | 4/400. |
| Q11.1 | B. Join drawings, schedules and calculations | The shared key. |
| Q11.2 | B. NOT VERIFIED | A pass is not evidence. |
| Q11.3 | B. The people who approve | Never by the software. |
| Q11.4 | B. A sketch, not evidence | It must trace to something. |
| Q12.1 | B. Factory acceptance test | A unit test at the factory. |
| Q12.2 | B. The whole chain under failure | The chain under failure. |
| Q12.3 | B. Capacity at a known resistive load, not the full behaviour | It is a different load. |
| Q12.4 | B. The specification and manufacturer data | Not from training material. |
