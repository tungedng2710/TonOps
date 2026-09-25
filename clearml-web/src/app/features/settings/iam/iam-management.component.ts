import {ChangeDetectionStrategy, Component} from '@angular/core';
import {MatTabsModule} from '@angular/material/tabs';
import {IamUsersComponent} from './iam-users.component';
import {IamGroupsComponent} from './iam-groups.component';
import {IamAuditComponent} from './iam-audit.component';

@Component({
  selector: 'sm-iam-management',
  template: `<section class="iam-page"><header><h1>User Management</h1><p>Manage local users, groups, and identity audit events.</p></header><mat-tab-group animationDuration="0ms"><mat-tab label="Users"><sm-iam-users /></mat-tab><mat-tab label="Groups"><sm-iam-groups /></mat-tab><mat-tab label="Audit Log"><sm-iam-audit /></mat-tab></mat-tab-group></section>`,
  styles: [`.iam-page{padding:24px 32px;min-width:800px}header{margin-bottom:20px}h1{margin:0 0 6px;font-size:24px}p{color:var(--color-outline);margin:0}::ng-deep .mat-mdc-tab-body-content{padding-top:20px}`],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatTabsModule, IamUsersComponent, IamGroupsComponent, IamAuditComponent]
})
export class IamManagementComponent {}
