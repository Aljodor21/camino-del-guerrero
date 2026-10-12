import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';

import { MinutaService } from '../core/services/minuta';
import { mensajeError } from '../shared/errores';
import { MenuSemanal } from './menu-semanal/menu-semanal';
import { Mercado } from './mercado/mercado';
import { MiMinuta } from './mi-minuta/mi-minuta';
import { Portada } from '../shared/portada/portada';
import { guardarSeccionEnUrl } from '../shared/seccion-en-url';

type Seccion = 'menu' | 'mercado' | 'plan';

/** Menú, mercado y plan. Sin plan todavía: cómo armarlo. */
@Component({
  selector: 'app-nutricion',
  templateUrl: './nutricion.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, RouterLink, MessageModule, ProgressSpinnerModule, MenuSemanal, Mercado, MiMinuta],
})
export class Nutricion implements OnInit {
  protected minutas = inject(MinutaService);

  private route = inject(ActivatedRoute);

  protected seccion = signal<Seccion>(this.seccionInicial());
  protected error = signal('');
  protected cargando = computed(() => this.minutas.minutas() === null && !this.error());
  protected pestanas: { id: Seccion; label: string; icon: string }[] = [
    { id: 'menu', label: 'Menú', icon: 'pi pi-calendar' },
    { id: 'mercado', label: 'Mercado', icon: 'pi pi-shopping-cart' },
    { id: 'plan', label: 'Mi plan', icon: 'pi pi-file' },
  ];

  constructor() {
    guardarSeccionEnUrl(this.seccion);
  }

  private seccionInicial(): Seccion {
    const pedida = this.route.snapshot.queryParamMap.get('seccion');
    return pedida === 'mercado' || pedida === 'plan' ? pedida : 'menu';
  }

  ngOnInit(): void {
    this.minutas.cargar().subscribe({
      error: (err) => this.error.set(mensajeError(err, 'No pudimos cargar tu plan.')),
    });
  }
}
