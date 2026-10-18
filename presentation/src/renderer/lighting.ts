// Shared time-of-day lighting used when baking the resident and building models
// consumed by the Unreal Engine project.
export function lightingAt(time: number) {
  const minute = ((time % 1440) + 1440) % 1440, angle = (minute - 360) / 1440 * Math.PI * 2;
  const daylight = Math.max(0, Math.sin(angle));
  const dusk = Math.max(Math.exp(-(((minute - 355) / 65) ** 2)), Math.exp(-(((minute - 1070) / 65) ** 2)));
  const softDay = Math.sqrt(daylight);
  return { angle, daylight, dusk, sun: .4 + softDay * 2.3 + dusk * .75, ambient: .82 + softDay * .38 + dusk * .12, exposure: 1.12 - daylight * .08 };
}
