import {inject, Injectable, Renderer2, DOCUMENT} from '@angular/core';

import {ConfigurationService} from '@common/shared/services/configuration.service';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {Store} from '@ngrx/store';
import {setForcedTheme, setThemeColors} from '@common/core/actions/layout.actions';
import {selectThemeMode} from '@common/core/reducers/view.reducer';


@Injectable({
  providedIn: 'root'
})
export class ThemeService {
  private config = inject(ConfigurationService);
  private store = inject(Store);
  private renderer = inject(Renderer2);
  private readonly document = inject(DOCUMENT);

  constructor() {
    this.store.dispatch(setForcedTheme({theme: 'light', default: 'light'}));
    if (this.config.configuration().customStyle) {
      this.loadCustomStyle(this.config.configuration().customStyle);
    }

    this.store.select(selectThemeMode)
      .pipe(
        takeUntilDestroyed(),
      )
      .subscribe(theme => {
        this.renderer.removeClass(this.document.documentElement, 'light-mode');
        this.renderer.removeClass(this.document.documentElement, 'dark-mode');
        this.renderer.removeClass(this.document.documentElement, 'system-mode');
        this.renderer.addClass(this.document.documentElement, `${theme}-mode`);
        this.store.dispatch(setThemeColors({colors: this.getAllThemeColors()}));
      });

  }

  getAllThemeColors() {
    const res: Record<string, string> = {};
    if ('computedStyleMap' in document.body) {
      // Chrome
      const styles =  document.body.computedStyleMap();
      styles.forEach((val, key) => {
        if (key.startsWith('--color')) {
          res[key.replace('--color-','')] = val.toString();
        }
      });
    } else {
      // Firefox
      const styles = getComputedStyle(document.body);
      Array.from(styles).forEach(propertyName => {
        if (propertyName.startsWith('--color')) {
          res[propertyName.replace('--color-','')] = styles.getPropertyValue(propertyName);
        }
      });
    }
    return res;
  }

  loadCustomStyle(url: string) {
    const link: HTMLLinkElement = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = url;
    link.onerror = () => console.error(`Error loading custom style from ${url}`);

    const head: HTMLHeadElement = document.getElementsByTagName('head')[0];
    head.appendChild(link);
  }
}
