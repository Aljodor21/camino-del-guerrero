/** Clases de una opción tipo chip dentro de un radiogroup. */
export function clasesChip(activa: boolean): string {
  const base =
    'px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-guerrero-red';
  return activa
    ? `${base} border-guerrero-red bg-red-50 dark:bg-guerrero-red/10 text-guerrero-red`
    : `${base} border-gray-200 dark:border-dark-700 text-gray-600 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600`;
}
