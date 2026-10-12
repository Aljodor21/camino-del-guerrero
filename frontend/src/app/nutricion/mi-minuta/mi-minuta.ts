import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';

import { MinutaService } from '../../core/services/minuta';
import { VisorService } from '../../core/services/visor';
import { Minuta, ReglaPorFuera, TiempoComida } from '../../core/models/minuta.model';
import { OPCIONES_POR_FUERA, TIEMPOS_COMIDA } from '../../core/constants/nutricion';
import { clasesChip } from '../../shared/chip';
import { mensajeError } from '../../shared/errores';
import { formatearFecha, formatearNumero } from '../../shared/fechas';
import { TablaMinuta } from '../tabla-minuta/tabla-minuta';

/** La minuta vigente: fija. Lo único que se ajusta aquí es qué comidas se hacen por fuera. */
import { Ayuda } from '../../shared/ayuda/ayuda';

@Component({
  selector: 'app-mi-minuta',
  templateUrl: './mi-minuta.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Ayuda, RouterLink, ButtonModule, MessageModule, TablaMinuta],
})
export class MiMinuta implements OnInit {
  protected servicio = inject(MinutaService);
  private visor = inject(VisorService);

  protected tiempos = TIEMPOS_COMIDA;
  protected opcionesPorFuera = OPCIONES_POR_FUERA;
  protected clasesChip = clasesChip;
  protected formatearFecha = formatearFecha;
  protected num = formatearNumero;

  protected porFuera = signal<Partial<Record<TiempoComida, ReglaPorFuera>>>({});
  protected guardando = signal(false);
  protected guardado = signal(false);
  protected error = signal('');

  protected ejemplo = computed(() => {
    const m = this.servicio.vigente();
    return m
      ? m.tiempos.filter((t) => m.menu_ejemplo[t]).map((t) => ({ t, texto: m.menu_ejemplo[t]! }))
      : [];
  });

  ngOnInit(): void {
    this.servicio.preferencias().subscribe({ next: (p) => this.porFuera.set(p.por_fuera) });
  }

  protected reglaDe(tiempo: TiempoComida): ReglaPorFuera | null {
    return this.porFuera()[tiempo] ?? null;
  }

  protected cambiarPorFuera(tiempo: TiempoComida, regla: ReglaPorFuera | null): void {
    const anterior = this.porFuera();
    const siguiente = { ...anterior };
    if (regla) siguiente[tiempo] = regla;
    else delete siguiente[tiempo];
    this.porFuera.set(siguiente);
    this.guardando.set(true);
    this.guardado.set(false);
    this.error.set('');
    this.servicio.guardarPreferencias({ por_fuera: siguiente }).subscribe({
      next: () => {
        this.guardando.set(false);
        this.guardado.set(true);
      },
      error: (err) => {
        this.porFuera.set(anterior);
        this.error.set(mensajeError(err, 'No pudimos guardar el cambio.'));
        this.guardando.set(false);
      },
    });
  }

  protected verOriginal(minuta: Minuta): void {
    this.visor.abrir('Tu plan, el original', this.servicio.archivo(minuta.id));
  }
}
