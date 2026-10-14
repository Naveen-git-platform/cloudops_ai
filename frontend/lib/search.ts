/** Case-insensitive substring match of `query` against any of `fields`. */
export const matchesQuery = (query: string, ...fields: string[]) => {
  const needle = query.trim().toLowerCase();
  return fields.some((field) => field.toLowerCase().includes(needle));
};
