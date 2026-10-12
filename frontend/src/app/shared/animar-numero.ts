/**
 * Lleva un valor de 0 a 1 en `ms` milisegundos, con desaceleración, y avisa cada cuadro.
 * Con "reducir movimiento" salta directo al final. Devuelve cómo cancelarlo.
 */
export function animarProgreso(alCambiar: (valor: number) => void, ms = 900): () => void {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    alCambiar(1);
    return () => undefined;
  }
  const inicio = performance.now();
  let cuadro = 0;
  const paso = (ahora: number) => {
    const t = Math.min(1, (ahora - inicio) / ms);
    alCambiar(1 - Math.pow(1 - t, 3));
    if (t < 1) cuadro = requestAnimationFrame(paso);
  };
  alCambiar(0);
  cuadro = requestAnimationFrame(paso);
  return () => cancelAnimationFrame(cuadro);
}
