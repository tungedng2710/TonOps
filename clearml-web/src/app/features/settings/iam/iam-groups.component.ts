import {ChangeDetectionStrategy, Component, DestroyRef, inject, signal} from '@angular/core';
import {MatButtonModule} from '@angular/material/button';
import {MatDialog} from '@angular/material/dialog';
import {MatTableModule} from '@angular/material/table';
import {filter} from 'rxjs/operators';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {IamGroup, IamUser} from './iam.models';
import {IamGroupDialogComponent, IamMemberDialogComponent} from './iam-group-dialog.component';
import {ConfirmDialogComponent} from '@common/shared/ui-components/overlay/confirm-dialog/confirm-dialog.component';
import {IamNotificationsService} from './iam-notifications.service';

@Component({
  selector: 'sm-iam-groups',
  template: `
    <div class="iam-panel">
      <div class="toolbar"><h2>Groups</h2><span class="spacer"></span><button mat-flat-button type="button" (click)="editGroup()">Add group</button></div>
      <div class="split">
        <div class="table-scroll">
          <table mat-table [dataSource]="groups()" class="groups-table">
            <ng-container matColumnDef="name"><th mat-header-cell *matHeaderCellDef>Group</th><td mat-cell *matCellDef="let group"><button mat-button (click)="select(group)">{{group.name}}</button></td></ng-container>
            <ng-container matColumnDef="description"><th mat-header-cell *matHeaderCellDef>Description</th><td mat-cell *matCellDef="let group">{{group.description || '—'}}</td></ng-container>
            <ng-container matColumnDef="members"><th mat-header-cell *matHeaderCellDef>Members</th><td mat-cell *matCellDef="let group">{{group.member_count}}</td></ng-container>
            <ng-container matColumnDef="actions"><th mat-header-cell *matHeaderCellDef class="actions-header">Actions</th><td mat-cell *matCellDef="let group" class="actions-cell"><div class="row-actions"><button mat-stroked-button type="button" class="edit-button" (click)="editGroup(group)" [attr.aria-label]="'Edit ' + group.name">Edit</button><button mat-icon-button type="button" (click)="removeGroup(group)" [attr.aria-label]="'Delete ' + group.name"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 3h4m-8 4 1 13h10l1-13M10 11v5m4-5v5"/></svg></button></div></td></ng-container>
            <tr mat-header-row *matHeaderRowDef="columns"></tr><tr mat-row *matRowDef="let row; columns: columns" [class.selected]="selected()?.id === row.id"></tr>
          </table>
          @if (!groups().length) { <div class="empty-state"><strong>No groups yet</strong><p>Add a group to organize access.</p></div> }
        </div>
        <aside>
          @if (selected(); as group) {
            <div class="toolbar"><h3>{{group.name}} members</h3><span class="spacer"></span><button mat-button (click)="addMember(group)">Add member</button></div>
            @for (member of group.members; track member.id) {
              <div class="member"><span>{{member.username}} <small>{{member.display_name}}</small></span><button mat-icon-button (click)="removeMember(group, member)" [attr.aria-label]="'Remove ' + member.username"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>
            } @empty { <p class="empty">This group has no members.</p> }
          } @else {
            <div class="empty-state"><strong>Group members</strong><p>Select a group to view and manage its members.</p></div>
          }
        </aside>
      </div>
    </div>
  `,
  styleUrls: ['./iam.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, MatTableModule]
})
export class IamGroupsComponent {
  private api = inject(ApiIamService);
  private dialog = inject(MatDialog);
  private notifications = inject(IamNotificationsService);
  private destroyRef = inject(DestroyRef);
  protected groups = signal<IamGroup[]>([]);
  protected selected = signal<IamGroup | null>(null);
  protected columns = ['name', 'description', 'members', 'actions'];

  constructor() { this.reload(); }
  private reload() { this.api.listGroups({page_size: 200}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
    next: result => this.groups.set(result.groups ?? []), error: error => this.notifications.error('Unable to load groups', error)
  }); }
  protected select(group: IamGroup) { this.api.getGroup(group.id).subscribe({
    next: result => this.selected.set(result.group), error: error => this.notifications.error('Unable to load group', error)
  }); }
  protected editGroup(group?: IamGroup) {
    this.dialog.open(IamGroupDialogComponent, {data: {group}, width: '500px', maxWidth: 'calc(100vw - 32px)'}).afterClosed().pipe(filter(Boolean), takeUntilDestroyed(this.destroyRef)).subscribe(value => {
      (group ? this.api.updateGroup(group.id, value) : this.api.createGroup(value)).subscribe({
        next: () => this.reload(), error: error => this.notifications.error('Unable to save group', error)
      });
    });
  }
  protected removeGroup(group: IamGroup) {
    this.confirm(`Delete group “${group.name}”?`, 'Users will not be deleted.', 'Delete', () => this.api.deleteGroup(group.id).subscribe({
      next: () => { if (this.selected()?.id === group.id) this.selected.set(null); this.reload(); },
      error: error => this.notifications.error('Unable to delete group', error)
    }));
  }
  protected addMember(group: IamGroup) {
    this.dialog.open(IamMemberDialogComponent, {data: {exclude: group.members?.map(member => member.id) ?? []}, width: '500px', maxWidth: 'calc(100vw - 32px)'}).afterClosed().pipe(filter(Boolean), takeUntilDestroyed(this.destroyRef)).subscribe(userId => this.api.addGroupMember(group.id, userId).subscribe({
      next: () => { this.select(group); this.reload(); }, error: error => this.notifications.error('Unable to add group member', error)
    }));
  }
  protected removeMember(group: IamGroup, user: IamUser) {
    this.confirm(`Remove ${user.username} from ${group.name}?`, '', 'Remove', () => this.api.removeGroupMember(group.id, user.id).subscribe({
      next: () => { this.select(group); this.reload(); }, error: error => this.notifications.error('Unable to remove group member', error)
    }));
  }
  private confirm(title: string, body: string, yes: string, action: () => void) {
    this.dialog.open(ConfirmDialogComponent, {data: {title, body, yes, no: 'Cancel'}}).afterClosed().pipe(filter(result => result?.isConfirmed), takeUntilDestroyed(this.destroyRef)).subscribe(action);
  }
}
