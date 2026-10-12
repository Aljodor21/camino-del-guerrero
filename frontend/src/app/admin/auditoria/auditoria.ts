import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { Cliente, Huella, Huellas, ResumenAuditoria } from '../../core/models/auditoria.model';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, hoyISO, sumarDias } from '../../shared/fechas';
import { Pestana, Pestanas } from '../../shared/pestanas/pestanas';
import { environment } from '../../../environments/environment';

const API = `${environment.apiUrl}/auditoria`;

type Vista = 'resumen' | 'huellas';
type Rango = 1 | 7 | 30 | 90;

const RANGOS: { dias: Rango; label: string }[] = [
  { dias: 1, label: 'Hoy' },
  { dias: 7, label: '7 días' },
  { dias: 30, label: '30 días' },
  { dias: 90, label: '90 días' },
];

/** Quién usa la app, desde qué dispositivo y qué consulta. Solo la ve el administrador. */
@Component({
  selector: 'app-auditoria',
  templateUrl: './auditoria.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ButtonModule, MessageModule, Pestanas],
})
export class Auditoria implements OnInit {
  private http = inject(HttpClient);

  protected clasesChip = clasesChip;
  protected rangos = RANGOS;
  protected pestanas: Pestana<Vista>[] = [
    { id: 'resumen', label: 'Resumen', icon: 'pi pi-chart-bar' },
    { id: 'huellas', label: 'Huellas', icon: 'pi pi-list' },
  ];

  protected vista = signal<Vista>('resumen');
  protected dias = signal<Rango>(7);
  protected cliente = signal<Cliente | ''>('');
  protected buscar = signal('');
  protected soloErrores = signal(false);
  protected conAutomaticos = signal(false);

  protected resumen = signal<ResumenAuditoria | null>(null);
  protected huellas = signal<Huella[]>([]);
  protected siguiente = signal<number | null>(null);
  protected cargando = signal(false);
  protected error = signal('');

  /** La barra más alta del día fija la escala de las demás. */
  protected maximoDia = computed(() =>
    Math.max(1, ...(this.resumen()?.por_dia.map((d) => d.total) ?? [1])),
  );

  ngOnInit(): void {
    this.cargar();
  }

  protected cambiar(): void {
    this.cargar();
  }

  protected elegirRango(d: Rango): void {
    this.dias.set(d);
    this.cargar();
  }

  protected elegirCliente(c: Cliente | ''): void {
    this.cliente.set(c);
    this.cargar();
  }

  protected alternar(campo: 'soloErrores' | 'conAutomaticos'): void {
    this[campo].update((v) => !v);
    this.cargar();
  }

  protected cargar(): void {
    this.cargando.set(true);
    this.error.set('');
    const params = this.parametros();
    this.http.get<ResumenAuditoria>(`${API}/resumen/`, { params }).subscribe({
      next: (r) => this.resumen.set(r),
      error: (e) => this.fallo(e),
    });
    this.http.get<Huellas>(`${API}/eventos/`, { params }).subscribe({
      next: (h) => {
        this.huellas.set(h.resultados);
        this.siguiente.set(h.siguiente);
        this.cargando.set(false);
      },
      error: (e) => this.fallo(e),
    });
  }

  protected masHuellas(): void {
    const antes = this.siguiente();
    if (antes === null) return;
    this.cargando.set(true);
    this.http
      .get<Huellas>(`${API}/eventos/`, { params: this.parametros().set('antes', antes) })
      .subscribe({
        next: (h) => {
          this.huellas.update((l) => [...l, ...h.resultados]);
          this.siguiente.set(h.siguiente);
          this.cargando.set(false);
        },
        error: (e) => this.fallo(e),
      });
  }

  private parametros(): HttpParams {
    let p = new HttpParams()
      .set('desde', sumarDias(hoyISO(), 1 - this.dias()))
      .set('hasta', hoyISO());
    if (this.cliente()) p = p.set('cliente', this.cliente());
    if (this.buscar().trim()) p = p.set('q', this.buscar().trim());
    if (this.soloErrores()) p = p.set('errores', '1');
    if (this.conAutomaticos()) p = p.set('automaticos', '1');
    return p;
  }

  private fallo(e: unknown): void {
    this.cargando.set(false);
    this.error.set(mensajeError(e, 'No pudimos cargar la auditoría.'));
  }

  protected altura(total: number): number {
    return Math.max(4, Math.round((total / this.maximoDia()) * 100));
  }

  protected dia(iso: string): string {
    return formatearFecha(iso, 'dia');
  }

  protected momento(iso: string): string {
    return new Date(iso).toLocaleString('es-CO', {
      day: 'numeric',
      month: 'short',
      hour: 'numeric',
      minute: '2-digit',
      second: '2-digit',
    });
  }

  protected nombreCliente(c: Cliente | ''): string {
    return c === 'app' ? 'App' : c === 'web' ? 'Navegador' : '—';
  }

  /** Verde si salió bien, ámbar si fue un error de quien pidió, rojo si falló el servidor. */
  protected tonoEstado(estado: number | null): string {
    if (estado === null) return 'bg-gray-500/15 text-gray-600 dark:text-gray-300';
    if (estado < 400) return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400';
    return estado < 500
      ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
      : 'bg-guerrero-red/15 text-guerrero-red';
  }
}
