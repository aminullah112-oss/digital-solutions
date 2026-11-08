# Short-circuit, protection and earthing framework (Stage 5)

Preliminary and educational. Not a study.

**No values are invented for utility, manufacturer or site data.** The shipped configuration holds no utility fault level or X/R, transformer impedance or X/R, generator reactance or X/R, soil resistivity or grid geometry. A case is calculated only when every input it needs is supplied. Otherwise the check shows NOT CALCULATED / NOT VERIFIED, lists the missing parameters, explains their impact and names the source document. The transformer-limited upper bound (infinite source behind one transformer) needs only the transformer data, so it is the first result to appear. Even when every input is supplied, results stay NOT VERIFIED until a reviewer confirms the source documents.

## Short-circuit method (IEC 60909, maximum three-phase)
- Utility: Z_Q = c Un^2 / S''kQ at MV, referred to LV by (Un_LV/Un_MV)^2. At MV, Ik'' = S''kQ / (sqrt3 Un).
- Transformer: Z_T = (uk/100) Un^2 / Sr, with the correction factor K_T = 0.95 c_max / (1 + 0.6 x_T).
- Generators: Z_G = (x''d/100) Un^2 / Sg, with K_G = c_max / (1 + x''d sin(phi_r)), n units in parallel.
- Ik'' = c Un / (sqrt3 |Z|). Peak ip = kappa sqrt2 Ik'' with kappa = 1.02 + 0.98 exp(-3 R/X). Thermal equivalent Ith = Ik'' sqrt(m + n), n = 1.
- Design value at the LV bus: the larger of the utility case and the generator case (open transition). If the design allows generators in parallel with the utility (`short_circuit.generator_parallel_with_utility`), the arithmetic sum is used. The sum is shown either way, as a warning of what closed transition would cost.
- Not included: motor contribution, cable and busduct impedance up to the bus (conservative), minimum fault current, the second path.

## Checks
- Equipment: busduct, LV and MV switchgear short-circuit ratings and protection-device breaking and making capacity are compared with the fault level when supplied (PASS or FAIL). With no rating they are NOT VERIFIED.
- Cables: adiabatic equation S = I sqrt(t) / k, fault taken at the bus the cable leaves and split over parallel runs. The clearing time is a placeholder until a coordination study.
- Practical limit: `short_circuit.lv_fault_level_limit_ka` is an Ohmetry policy, not a standard limit.

## Earthing screening (IEEE 80)
Rg = rho [1/LT + 1/sqrt(20 A) (1 + 1/(1 + h sqrt(20/A)))]. GPR = Ig x Rg when the earth-fault current is supplied. Tolerable touch voltage (70 kg) = (1000 + 1.5 Cs rho_s) x 0.157 / sqrt(ts). A GPR below the tolerable touch voltage is a screening pass only: mesh and step voltages are not calculated, and a higher GPR needs detailed analysis.

## Not covered
Protection coordination (discrimination), arc-flash, earth-fault loop impedance and disconnection times, minimum fault current and lightning protection. Each needs manufacturer curves or a dedicated study.
