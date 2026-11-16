import {ChangeDetectionStrategy, Component, computed, inject, signal} from '@angular/core';
import {NavigationEnd, Router, RouterLink, RouterOutlet} from '@angular/router';
import {filter} from 'rxjs/operators';
import {takeUntilDestroyed, toSignal} from '@angular/core/rxjs-interop';
import {Store} from '@ngrx/store';
import {selectRouterParams} from '@common/core/reducers/router-reducer';
import {selectSelectedProject} from '@common/core/reducers/projects.reducer';

@Component({
  selector: 'sm-model-management',
  templateUrl: './model-management.component.html',
  styleUrl: './model-management.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink]
})
export class ModelManagementComponent {
  private router = inject(Router);
  private store = inject(Store);
  private navigation = toSignal(this.router.events.pipe(filter(event => event instanceof NavigationEnd)));
  protected currentUrl = computed(() => this.navigation()?.urlAfterRedirects || this.router.url);
  protected endpointsView = computed(() => this.currentUrl().startsWith('/models/endpoints'));
  protected loadingView = computed(() => this.currentUrl().split('?')[0] === '/models/endpoints/loading');
  protected hubUrl = signal(this.router.parseUrl('/models/registry/*'));
  protected endpointsUrl = signal(this.router.parseUrl('/models/endpoints/active'));
  protected params = this.store.selectSignal(selectRouterParams);
  protected project = this.store.selectSignal(selectSelectedProject);
  protected projectScoped = computed(() => !this.endpointsView() &&
    !!this.params().projectId && this.params().projectId !== '*');

  constructor() {
    this.router.events.pipe(filter(event => event instanceof NavigationEnd), takeUntilDestroyed())
      .subscribe(event => {
        if (event.urlAfterRedirects.startsWith('/models/registry/')) this.hubUrl.set(this.router.parseUrl(event.urlAfterRedirects));
        if (event.urlAfterRedirects.startsWith('/models/endpoints/')) this.endpointsUrl.set(this.router.parseUrl(event.urlAfterRedirects));
      });
  }
}
