import {ChangeDetectionStrategy, Component} from '@angular/core';
import {MatTabsModule} from '@angular/material/tabs';
import {IamUsersComponent} from './iam-users.component';
import {IamGroupsComponent} from './iam-groups.component';
import {IamAuditComponent} from './iam-audit.component';

@Component({
  selector: 'sm-iam-management',
  template: `
    <main class="iam-page">
      <header class="page-heading">
        <p class="eyebrow">ADMINISTRATION</p>
        <h1>User management</h1>
        <p>Manage accounts, group access, and identity activity in your workspace.</p>
      </header>
      <mat-tab-group animationDuration="0ms" class="iam-tabs">
        <mat-tab label="Users"><sm-iam-users /></mat-tab>
        <mat-tab label="Groups"><sm-iam-groups /></mat-tab>
        <mat-tab label="Audit log"><sm-iam-audit /></mat-tab>
      </mat-tab-group>
    </main>
  `,
  styles: [`
    .iam-page { width: min(100%, 1320px); margin: 0 auto; padding: 44px 36px 80px; color: var(--color-on-surface); }
    .page-heading { margin-bottom: 28px; }
    .eyebrow { margin: 0 0 10px; color: var(--color-primary); font-size: 11px; font-weight: 700; letter-spacing: 0.13em; }
    h1 { margin: 0 0 8px; font-size: clamp(28px, 3vw, 36px); font-weight: 700; letter-spacing: -0.035em; }
    .page-heading > p:last-child { margin: 0; color: var(--color-on-surface-variant); }
    .iam-tabs { min-width: 0; }
    ::ng-deep .mat-mdc-tab-body-content { padding-top: 24px; }
    @media (max-width: 700px) { .iam-page { padding: 28px 18px 56px; } }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatTabsModule, IamUsersComponent, IamGroupsComponent, IamAuditComponent]
})
export class IamManagementComponent {}
