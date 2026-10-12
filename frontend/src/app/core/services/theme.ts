import { Injectable, signal, effect } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly STORAGE_KEY = 'cdg_theme';

  isDark = signal<boolean>(this._loadPreference());

  constructor() {
    effect(() => {
      document.documentElement.classList.toggle('dark', this.isDark());
      localStorage.setItem(this.STORAGE_KEY, this.isDark() ? 'dark' : 'light');
    });
  }

  toggle(): void {
    this.isDark.update((v) => !v);
  }

  private _loadPreference(): boolean {
    const stored = localStorage.getItem(this.STORAGE_KEY);
    if (stored) return stored === 'dark';
    return true;
  }
}
