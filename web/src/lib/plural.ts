// Slovak plural: 1 snímka, 2–4 snímky, 0 and 5+ snímok
export const pluralSk = (count: number, one: string, few: string, many: string) =>
  count === 1 ? one : count >= 2 && count <= 4 ? few : many;
