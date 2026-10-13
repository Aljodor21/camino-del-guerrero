import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { TextareaModule } from 'primeng/textarea';

import { GRUPOS_MINUTA, TIEMPOS_COMIDA } from '../../core/constants/nutricion';
import { Avances, PedidoComida } from '../../core/models/comidas.model';
import { GrupoMinuta, TiempoComida } from '../../core/models/minuta.model';
import { ComidasService } from '../../core/services/comidas';
import { AvisosService } from '../../core/services/avisos';
import { CelebracionesService } from '../../core/services/celebraciones';
import { prepararFoto } from '../../core/services/foto';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { formatearFecha } from '../../shared/fechas';
import { Portada } from '../../shared/portada/portada';

const OPCIONES: { valor: number; label: string }[] = [
  { valor: 1, label: 'Todo' },
  { valor: 0.75, label: 'Casi todo' },
  { valor: 0.5, label: 'La mitad' },
  { valor: 0.25, label: 'Poco' },
  { valor: 0, label: 'Nada' },
];

/**
 * Contar lo que se comió: cuánto de cada grupo que pedía la minuta, una nota y, si se
 * quiere, una foto. Con eso se calcula qué tanto se cumple el plan.
 */
@Component({
  selector: 'app-contar-comida',
  templateUrl: './contar.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, RouterLink, ButtonModule, MessageModule, TextareaModule],
})
export class ContarComida implements OnInit {
  private ruta = inject(ActivatedRoute);
  private router = inject(Router);
  private comidas = inject(ComidasService);
  private avisos = inject(AvisosService);
  private celebraciones = inject(CelebracionesService);

  protected opciones = OPCIONES;
  protected clasesChip = clasesChip;
  protected grupos = GRUPOS_MINUTA;

  protected pedido = signal<PedidoComida | null>(null);
  protected cargando = signal(true);
  protected error = signal('');
  protected enviando = signal(false);
  protected avances = signal<Avances>({});
  protected nota = signal('');
  protected foto = signal<Blob | null>(null);
  protected vista = signal<string | null>(null);
  protected leyendoFoto = signal(false);

  protected titulo = computed(() => {
    const p = this.pedido();
    return p ? `Tu ${TIEMPOS_COMIDA[p.tiempo].label.toLowerCase()}` : 'Cuenta tu comida';
  });
  protected cuando = computed(() => {
    const p = this.pedido();
    return p ? formatearFecha(p.fecha) : '';
  });
  protected completo = computed(() => {
    const p = this.pedido();
    return !!p && p.grupos.every((g) => this.avances()[g.grupo] !== undefined);
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => this.soltarVista());
  }

  ngOnInit(): void {
    const q = this.ruta.snapshot.queryParamMap;
    const tiempo = q.get('tiempo') as TiempoComida | null;
    if (!tiempo || !(tiempo in TIEMPOS_COMIDA)) {
      this.cargando.set(false);
      this.error.set('Falta decir de qué comida es. Ábrela desde tu aviso.');
      return;
    }
    this.comidas.pedido(tiempo, q.get('fecha') ?? undefined).subscribe({
      next: (p) => {
        this.pedido.set(p);
        this.cargando.set(false);
      },
      error: (e) => {
        this.cargando.set(false);
        this.error.set(mensajeError(e, 'No pudimos cargar tu comida.'));
      },
    });
  }

  protected elegir(grupo: GrupoMinuta, valor: number): void {
    this.avances.update((a) => ({ ...a, [grupo]: valor }));
  }

  protected todoElPlan(): void {
    const p = this.pedido();
    if (p) this.avances.set(Object.fromEntries(p.grupos.map((g) => [g.grupo, 1])));
  }

  protected leerNota(evento: Event): void {
    this.nota.set((evento.target as HTMLTextAreaElement).value);
  }

  protected async elegirFoto(evento: Event): Promise<void> {
    const campo = evento.target as HTMLInputElement;
    const archivo = campo.files?.[0];
    campo.value = '';
    if (!archivo) return;
    this.error.set('');
    this.leyendoFoto.set(true);
    try {
      const foto = await prepararFoto(archivo);
      this.soltarVista();
      this.foto.set(foto);
      this.vista.set(URL.createObjectURL(foto));
    } catch {
      this.error.set('No pudimos leer esa foto. Prueba con una imagen JPG o PNG.');
    } finally {
      this.leyendoFoto.set(false);
    }
  }

  protected quitarFoto(): void {
    this.soltarVista();
    this.foto.set(null);
    this.vista.set(null);
  }

  protected enviar(): void {
    const p = this.pedido();
    if (!p || !this.completo()) return;
    this.enviando.set(true);
    this.error.set('');
    this.comidas
      .contar({
        tiempo: p.tiempo,
        fecha: p.fecha,
        avances: this.avances(),
        nota: this.nota().trim(),
        foto: this.foto(),
      })
      .subscribe({
        next: () => {
          // El aviso de esta comida ya se resolvió en el servidor.
          this.celebraciones.registro('comer');
          this.avisos.cargar().subscribe({ error: () => undefined });
          void this.router.navigate(['/cumplimiento'], { queryParams: { listo: p.tiempo } });
        },
        error: (e) => {
          this.enviando.set(false);
          this.error.set(mensajeError(e, 'No pudimos guardarlo. Intenta de nuevo.'));
        },
      });
  }

  private soltarVista(): void {
    const url = this.vista();
    if (url) URL.revokeObjectURL(url);
  }
}
