import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { InputTextModule } from 'primeng/inputtext';
import { MessageModule } from 'primeng/message';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { ButtonModule } from 'primeng/button';

import { environment } from '../../../environments/environment';
import { mensajeError } from '../../shared/errores';
import { Portada } from '../../shared/portada/portada';

interface Alimento {
  id: number;
  grupo: string;
  subgrupo: string;
  nombre: string;
  gramos: number | null;
  medida: string;
}

const NOMBRE_GRUPO: Record<string, string> = {
  sustitutos: 'Sustitutos',
  lacteos: 'Lácteos',
  carnes: 'Carnes',
  leguminosas: 'Leguminosas',
  cereales: 'Cereales, raíces, tubérculos y plátanos',
  verduras: 'Verduras',
  frutas: 'Frutas',
  grasas: 'Aceites vegetales y aguacate',
  semillas: 'Semillas y oleaginosas',
  azucares: 'Azúcares y dulces',
  libres: 'Libres',
};

const sinTildes = (t: string) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** La lista de intercambios que usa el plan, para verla por grupos y saber cómo cambiarla. */
@Component({
  selector: 'app-lista-alimentos',
  templateUrl: './lista-alimentos.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Portada, InputTextModule, MessageModule, ProgressSpinnerModule, ButtonModule],
})
export class ListaAlimentos implements OnInit {
  private http = inject(HttpClient);

  protected alimentos = signal<Alimento[]>([]);
  protected cargando = signal(true);
  protected error = signal('');
  protected busqueda = signal('');

  /** Los grupos con sus alimentos, filtrados por lo que se busca. */
  protected grupos = computed(() => {
    const q = sinTildes(this.busqueda().trim());
    const filtrados = this.alimentos().filter(
      (a) => !q || sinTildes(a.nombre).includes(q) || sinTildes(a.subgrupo).includes(q),
    );
    const mapa = new Map<string, Alimento[]>();
    for (const a of filtrados) mapa.set(a.grupo, [...(mapa.get(a.grupo) ?? []), a]);
    return Array.from(mapa, ([id, items]) => ({ id, nombre: NOMBRE_GRUPO[id] ?? id, items }));
  });
  protected total = computed(() => this.alimentos().length);
  protected encontrados = computed(() => this.grupos().reduce((n, g) => n + g.items.length, 0));

  protected ejemplo = [
    { grupo: 'cereales', subgrupo: 'Cereales', alimento: 'Arepa delgada de maíz blanco trillado', gramos: '56', medida: '1 unidad pequeña' },
    { grupo: 'frutas', subgrupo: 'Frutas', alimento: 'Mango', gramos: '110', medida: '½ unidad mediana' },
    { grupo: 'lacteos', subgrupo: 'Lácteos', alimento: 'Yogurt griego natural descremado', gramos: '100', medida: '1 vaso pequeño' },
  ];

  ngOnInit(): void {
    this.http.get<Alimento[]>(`${environment.apiUrl}/nutricion/intercambios/`).subscribe({
      next: (lista) => {
        this.alimentos.set(lista);
        this.cargando.set(false);
      },
      error: (err) => {
        this.error.set(mensajeError(err, 'No pudimos cargar la lista.'));
        this.cargando.set(false);
      },
    });
  }

  /** El archivo es privado y se pide con el token: se baja y se guarda como un CSV. */
  protected descargar(): void {
    this.http
      .get(`${environment.apiUrl}/nutricion/intercambios/csv/`, { responseType: 'blob' })
      .subscribe({
        next: (blob) => {
          const url = URL.createObjectURL(blob);
          const enlace = document.createElement('a');
          enlace.href = url;
          enlace.download = 'lista-de-intercambios.csv';
          enlace.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        },
        error: (err) => this.error.set(mensajeError(err, 'No pudimos descargar la lista.')),
      });
  }
}
