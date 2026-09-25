import {Component, inject, signal} from '@angular/core';
import {MatDrawer, MatDrawerContainer, MatDrawerContent} from '@angular/material/sidenav';
import {MatListModule} from '@angular/material/list';
import {RouterLink, RouterLinkActive, RouterOutlet} from '@angular/router';
import {AdminFooterComponent} from '@common/settings/admin/admin-footer/admin-footer.component';
import {Store} from '@ngrx/store';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';
import {ApiIamService} from '~/business-logic/api-services/iam.service';

@Component({
  selector: 'sm-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['../../webapp-common/settings/settings.component.scss'],
  imports: [
    MatDrawerContainer,
    MatDrawer,
    MatListModule,
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

  constructor() {
    this.iam.status().subscribe({
      next: result => this.iamEnabled.set(result.enabled),
      error: () => this.iamEnabled.set(false)
    });
  }
}
