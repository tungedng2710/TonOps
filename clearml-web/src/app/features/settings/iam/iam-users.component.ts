import {ChangeDetectionStrategy, Component, DestroyRef, inject, signal} from '@angular/core';
import {DatePipe} from '@angular/common';
import {FormControl, ReactiveFormsModule} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatDialog} from '@angular/material/dialog';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {MatTableModule} from '@angular/material/table';
import {MatPaginatorModule, PageEvent} from '@angular/material/paginator';
import {MatMenuModule} from '@angular/material/menu';
import {MatSortModule, Sort} from '@angular/material/sort';
import {debounceTime, filter} from 'rxjs/operators';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {IamUser} from './iam.models';
import {IamPasswordDialogComponent, IamUserDialogComponent} from './iam-user-dialog.component';
import {ConfirmDialogComponent} from '@common/shared/ui-components/overlay/confirm-dialog/confirm-dialog.component';
import {IamNotificationsService} from './iam-notifications.service';

@Component({
  selector: 'sm-iam-users',
  template: `
    <div class="iam-panel">
      <div class="panel-header">
        <div>
          <h2>Users</h2>
          <p>{{ total() }} {{ total() === 1 ? 'account' : 'accounts' }} in this workspace</p>
        </div>
        <button mat-flat-button type="button" (click)="openUser()">Add user</button>
      </div>
      <div class="filters">
        <mat-form-field appearance="outline" subscriptSizing="dynamic" class="search-field">
          <mat-label>Search by name or username</mat-label>
          <input matInput [formControl]="search" autocomplete="off">
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Role</mat-label>
          <mat-select [formControl]="role">
            <mat-option value="">All roles</mat-option>
            <mat-option value="admin">Admin</mat-option>
            <mat-option value="user">User</mat-option>
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic">
          <mat-label>Status</mat-label>
          <mat-select [formControl]="status">
            <mat-option value="">All statuses</mat-option>
            <mat-option value="active">Active</mat-option>
            <mat-option value="disabled">Disabled</mat-option>
          </mat-select>
        </mat-form-field>
      </div>
      <div class="table-scroll">
        <table mat-table matSort [dataSource]="users()" (matSortChange)="sortChanged($event)" class="users-table">
          <ng-container matColumnDef="username">
            <th mat-header-cell *matHeaderCellDef mat-sort-header="username">User</th>
            <td mat-cell *matCellDef="let u">
              <div class="user-cell">
                <span class="user-avatar" aria-hidden="true">{{ (u.display_name || u.username).charAt(0).toUpperCase() }}</span>
                <span class="user-details"><strong>{{ u.username }}</strong><small>{{ u.email || 'No email address' }}</small></span>
              </div>
            </td>
          </ng-container>
          <ng-container matColumnDef="name"><th mat-header-cell *matHeaderCellDef mat-sort-header="display_name">Display name</th><td mat-cell *matCellDef="let u">{{ u.display_name || '—' }}</td></ng-container>
          <ng-container matColumnDef="role"><th mat-header-cell *matHeaderCellDef mat-sort-header="role">Role</th><td mat-cell *matCellDef="let u"><span class="role-badge" [class.admin]="u.role === 'admin'">{{ u.role }}</span></td></ng-container>
          <ng-container matColumnDef="status"><th mat-header-cell *matHeaderCellDef mat-sort-header="status">Status</th><td mat-cell *matCellDef="let u"><span class="status-badge" [class.disabled]="u.status === 'disabled'">{{ u.status }}</span></td></ng-container>
          <ng-container matColumnDef="last"><th mat-header-cell *matHeaderCellDef mat-sort-header="last_login_at">Last login</th><td mat-cell *matCellDef="let u">{{ u.last_login_at ? (u.last_login_at | date:'mediumDate') : 'Never' }}</td></ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef class="actions-header">Actions</th>
            <td mat-cell *matCellDef="let u" class="actions-cell">
              <div class="row-actions">
                <button mat-stroked-button type="button" class="edit-button" (click)="openUser(u)" [attr.aria-label]="'Edit ' + u.username">Edit</button>
                <button mat-icon-button type="button" [matMenuTriggerFor]="actions" [attr.aria-label]="'More actions for ' + u.username">
                  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="currentColor">
                    <circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/>
                  </svg>
                </button>
                <mat-menu #actions="matMenu">
                  <button mat-menu-item (click)="toggle(u)">{{ u.status === 'active' ? 'Disable user' : 'Enable user' }}</button>
                  <button mat-menu-item (click)="reset(u)">Reset password</button>
                  <button mat-menu-item (click)="remove(u)">Delete user</button>
                </mat-menu>
              </div>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
        </table>
        @if (!users().length) {
          <div class="empty-state">
            <strong>No users found</strong>
            <p>Try changing the search or filters, or add a new user.</p>
          </div>
        }
      </div>
      <mat-paginator [length]="total()" [pageIndex]="page()" [pageSize]="pageSize" [pageSizeOptions]="[25,50,100]" (page)="paginate($event)"></mat-paginator>
    </div>
  `,
  styleUrls: ['./iam.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatTableModule, MatPaginatorModule, MatMenuModule, MatSortModule, DatePipe]
})
export class IamUsersComponent {
  private api = inject(ApiIamService);
  private dialog = inject(MatDialog);
  private notifications = inject(IamNotificationsService);
  private destroyRef = inject(DestroyRef);
  protected users = signal<IamUser[]>([]);
  protected total = signal(0);
  protected page = signal(0);
  protected pageSize = 50;
  protected columns = ['username', 'name', 'role', 'status', 'last', 'actions'];
  protected search = new FormControl('', {nonNullable: true});
  protected role = new FormControl('', {nonNullable: true});
  protected status = new FormControl('', {nonNullable: true});
  private sort = 'username';

  constructor() {
    this.search.valueChanges.pipe(debounceTime(250), takeUntilDestroyed()).subscribe(() => this.reload(true));
    this.role.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.reload(true));
    this.status.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.reload(true));
    this.reload();
  }

  protected reload(reset = false) {
    if (reset) this.page.set(0);
    this.api.listUsers({page: this.page(), page_size: this.pageSize, search: this.search.value, role: this.role.value || undefined, status: this.status.value || undefined, sort: this.sort})
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: result => { this.users.set(result.users ?? []); this.total.set(result.total); },
        error: error => this.notifications.error('Unable to load users', error)
      });
  }
  protected paginate(event: PageEvent) { this.page.set(event.pageIndex); this.pageSize = event.pageSize; this.reload(); }
  protected sortChanged(sort: Sort) { this.sort = sort.direction === 'desc' ? `-${sort.active}` : (sort.active || 'username'); this.reload(true); }
  protected openUser(user?: IamUser) {
    this.dialog.open(IamUserDialogComponent, {data: {user}, width: '560px', maxWidth: 'calc(100vw - 32px)'}).afterClosed().pipe(filter(Boolean), takeUntilDestroyed(this.destroyRef)).subscribe(value => {
      const request = user ? this.api.updateUser(user.id, value) : this.api.createUser(value);
      request.subscribe({next: () => this.reload(), error: error => this.notifications.error('Unable to save user', error)});
    });
  }
  protected toggle(user: IamUser) {
    const verb = user.status === 'active' ? 'Disable' : 'Enable';
    this.confirm(`${verb} user “${user.username}”?`, user.status === 'active' ? 'The user will no longer be able to log in.' : 'The user will be able to log in again.', verb, () =>
      (user.status === 'active' ? this.api.disableUser(user.id) : this.api.enableUser(user.id)).subscribe({
        next: () => this.reload(), error: error => this.notifications.error(`Unable to ${verb.toLowerCase()} user`, error)
      }));
  }
  protected reset(user: IamUser) {
    this.dialog.open(IamPasswordDialogComponent, {width: '480px'}).afterClosed().pipe(filter(value => value !== undefined), takeUntilDestroyed(this.destroyRef)).subscribe(password => {
      this.api.resetPassword(user.id, password).subscribe({
        next: result => {
          if (result.temporary_password) this.dialog.open(ConfirmDialogComponent, {data: {title: 'Temporary password', body: result.temporary_password, yes: 'Close', centerText: true}});
        },
        error: error => this.notifications.error('Unable to reset password', error)
      });
    });
  }
  protected remove(user: IamUser) {
    this.confirm(`Delete user “${user.username}”?`, 'This removes the account and its group memberships.', 'Delete', () => this.api.deleteUser(user.id).subscribe({
      next: () => this.reload(), error: error => this.notifications.error('Unable to delete user', error)
    }));
  }
  private confirm(title: string, body: string, yes: string, action: () => void) {
    this.dialog.open(ConfirmDialogComponent, {data: {title, body, yes, no: 'Cancel', iconClass: 'al-ico-alert'}}).afterClosed().pipe(filter(result => result?.isConfirmed), takeUntilDestroyed(this.destroyRef)).subscribe(action);
  }
}
