import {Component, inject, signal} from '@angular/core';
import {MatDrawer, MatDrawerContainer, MatDrawerContent} from '@angular/material/sidenav';
import {MatListModule} from '@angular/material/list';
import {RouterLink, RouterLinkActive, RouterOutlet} from '@angular/router';
import {AdminFooterComponent} from '@common/settings/admin/admin-footer/admin-footer.component';
import {Store} from '@ngrx/store';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {BreakpointObserver} from '@angular/cdk/layout';
import {MatButtonModule} from '@angular/material/button';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';

@Component({
  selector: 'sm-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['../../webapp-common/settings/settings.component.scss'],
  imports: [
    MatDrawerContainer,
    MatDrawer,
    MatListModule,
    MatButtonModule,
    RouterLinkActive,
    RouterLink,
    MatDrawerContent,
    RouterOutlet,
    AdminFooterComponent
  ]
})
export class SettingsComponent {
  private store = inject(Store);
  private iam = inject(ApiIamService);
  protected currentUser = this.store.selectSignal(selectCurrentUser);
  protected iamEnabled = signal(false);
  protected narrow = signal(false);

  constructor() {
    const breakpoints = inject(BreakpointObserver);
    this.narrow.set(breakpoints.isMatched('(max-width: 760px)'));
    breakpoints.observe('(max-width: 760px)').pipe(takeUntilDestroyed()).subscribe(result => this.narrow.set(result.matches));
    this.iam.status().subscribe({
      next: result => this.iamEnabled.set(result.enabled),
      error: () => this.iamEnabled.set(false)
    });
  }
}
