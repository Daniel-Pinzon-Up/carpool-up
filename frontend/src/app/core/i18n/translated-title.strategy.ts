import { Injectable, inject } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterStateSnapshot, TitleStrategy } from '@angular/router';
import { TranslocoService } from '@jsverse/transloco';
import { BehaviorSubject, combineLatest, switchMap } from 'rxjs';

/** El title de cada ruta es una clave de traduccion; se actualiza al cambiar de idioma. */
@Injectable({ providedIn: 'root' })
export class TranslatedTitleStrategy extends TitleStrategy {
  private readonly title = inject(Title);
  private readonly transloco = inject(TranslocoService);
  private readonly pageKey = new BehaviorSubject<string | undefined>(undefined);

  constructor() {
    super();
    combineLatest([this.pageKey, this.transloco.langChanges$])
      .pipe(
        switchMap(([key]) =>
          combineLatest([
            this.transloco.selectTranslate<string>(key ?? 'app.name'),
            this.transloco.selectTranslate<string>('app.name'),
          ]),
        ),
      )
      .subscribe(([page, appName]) => {
        this.title.setTitle(this.pageKey.value ? `${page} | ${appName}` : appName);
      });
  }

  override updateTitle(snapshot: RouterStateSnapshot): void {
    this.pageKey.next(this.buildTitle(snapshot));
  }
}
