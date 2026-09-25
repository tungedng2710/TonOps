import {DatePipe} from '@angular/common';
import {ChangeDetectionStrategy, Component, DestroyRef, inject, signal} from '@angular/core';
import {FormControl, ReactiveFormsModule} from '@angular/forms';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatTableModule} from '@angular/material/table';
import {MatPaginatorModule, PageEvent} from '@angular/material/paginator';
import {debounceTime} from 'rxjs/operators';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {IamAuditEvent} from './iam.models';
import {IamNotificationsService} from './iam-notifications.service';

@Component({
  selector: 'sm-iam-audit',
  template: `
    <div class="iam-panel">
      <div class="panel-header"><div><h2>Audit log</h2><p>Review account and access changes.</p></div></div>
      <div class="audit-filters">
        <mat-form-field appearance="outline" subscriptSizing="dynamic"><mat-label>Actor ID</mat-label><input matInput [formControl]="actor"></mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic"><mat-label>Action</mat-label><input matInput [formControl]="action"></mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic"><mat-label>Target ID</mat-label><input matInput [formControl]="target"></mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic"><mat-label>From</mat-label><input matInput type="datetime-local" [formControl]="from"></mat-form-field>
        <mat-form-field appearance="outline" subscriptSizing="dynamic"><mat-label>To</mat-label><input matInput type="datetime-local" [formControl]="to"></mat-form-field>
      </div>
      <div class="table-scroll">
        <table mat-table [dataSource]="events()">
          <ng-container matColumnDef="time"><th mat-header-cell *matHeaderCellDef>Time</th><td mat-cell *matCellDef="let event">{{event.timestamp | date:'medium'}}</td></ng-container>
          <ng-container matColumnDef="actor"><th mat-header-cell *matHeaderCellDef>Actor</th><td mat-cell *matCellDef="let event">{{event.actor_username || 'system'}}</td></ng-container>
          <ng-container matColumnDef="action"><th mat-header-cell *matHeaderCellDef>Action</th><td mat-cell *matCellDef="let event">{{event.action}}</td></ng-container>
          <ng-container matColumnDef="target"><th mat-header-cell *matHeaderCellDef>Target</th><td mat-cell *matCellDef="let event">{{event.target_type}} {{event.target_id}}</td></ng-container>
          <ng-container matColumnDef="ip"><th mat-header-cell *matHeaderCellDef>Source IP</th><td mat-cell *matCellDef="let event">{{event.source_ip || '—'}}</td></ng-container>
          <tr mat-header-row *matHeaderRowDef="columns"></tr><tr mat-row *matRowDef="let row; columns: columns"></tr>
        </table>
        @if (!events().length) { <div class="empty-state"><strong>No audit events found</strong><p>Try changing the filters.</p></div> }
      </div>
      <mat-paginator [length]="total()" [pageIndex]="page()" [pageSize]="pageSize" [pageSizeOptions]="[25,50,100]" (page)="paginate($event)"></mat-paginator>
    </div>
  `,
  styleUrls: ['./iam.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatTableModule, MatPaginatorModule, DatePipe]
})
export class IamAuditComponent {
  private api = inject(ApiIamService);
  private destroyRef = inject(DestroyRef);
  private notifications = inject(IamNotificationsService);
  protected events = signal<IamAuditEvent[]>([]);
  protected total = signal(0);
  protected page = signal(0);
  protected pageSize = 50;
  protected columns = ['time', 'actor', 'action', 'target', 'ip'];
  protected actor = new FormControl('', {nonNullable: true});
  protected action = new FormControl('', {nonNullable: true});
  protected target = new FormControl('', {nonNullable: true});
  protected from = new FormControl('', {nonNullable: true});
  protected to = new FormControl('', {nonNullable: true});
  constructor() {
    [this.actor, this.action, this.target, this.from, this.to].forEach(control => control.valueChanges.pipe(debounceTime(250), takeUntilDestroyed()).subscribe(() => { this.page.set(0); this.reload(); }));
    this.reload();
  }
  private reload() { this.api.listAudit({page: this.page(), page_size: this.pageSize, actor_user_id: this.actor.value || undefined, action: this.action.value || undefined, target_id: this.target.value || undefined, from_timestamp: this.from.value ? new Date(this.from.value).toISOString() : undefined, to_timestamp: this.to.value ? new Date(this.to.value).toISOString() : undefined}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
    next: result => { this.events.set(result.events ?? []); this.total.set(result.total); },
    error: error => this.notifications.error('Unable to load audit events', error)
  }); }
  protected paginate(event: PageEvent) { this.page.set(event.pageIndex); this.pageSize = event.pageSize; this.reload(); }
}
