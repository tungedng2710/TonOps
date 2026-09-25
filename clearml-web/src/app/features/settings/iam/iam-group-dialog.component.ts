import {Component, DestroyRef, inject, signal} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogModule, MatDialogRef} from '@angular/material/dialog';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatButtonModule} from '@angular/material/button';
import {MatSelectModule} from '@angular/material/select';
import {IamGroup, IamUser} from './iam.models';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {debounceTime} from 'rxjs/operators';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {IamNotificationsService} from './iam-notifications.service';

@Component({
  selector: 'sm-iam-group-dialog',
  template: `
    <h2 mat-dialog-title>{{data.group ? 'Edit group' : 'Add group'}}</h2>
    <mat-dialog-content><form [formGroup]="form" class="iam-form">
      <mat-form-field appearance="outline"><mat-label>Name</mat-label><input matInput formControlName="name"></mat-form-field>
      <mat-form-field appearance="outline"><mat-label>Description</mat-label><textarea matInput formControlName="description"></textarea></mat-form-field>
    </form></mat-dialog-content>
    <mat-dialog-actions align="end"><button mat-button mat-dialog-close>Cancel</button><button mat-flat-button color="primary" [disabled]="form.invalid" (click)="save()">Save</button></mat-dialog-actions>
  `,
  styles: [`.iam-form{display:flex;flex-direction:column;min-width:400px;padding-top:8px}`],
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule]
})
export class IamGroupDialogComponent {
  protected data = inject<{group?: IamGroup}>(MAT_DIALOG_DATA);
  private ref = inject(MatDialogRef<IamGroupDialogComponent>);
  protected form = new FormGroup({
    name: new FormControl(this.data.group?.name ?? '', [Validators.required, Validators.maxLength(64)]),
    description: new FormControl(this.data.group?.description ?? '', [Validators.maxLength(512)])
  });
  protected save() { this.ref.close(this.form.getRawValue()); }
}

@Component({
  selector: 'sm-iam-member-dialog',
  template: `
    <h2 mat-dialog-title>Add group member</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline" class="w-100"><mat-label>Search users</mat-label><input matInput [formControl]="search"></mat-form-field>
      <mat-form-field appearance="outline" class="w-100"><mat-label>User</mat-label>
        <mat-select [formControl]="user">
          @for (item of users(); track item.id) {
            <mat-option [value]="item.id">{{item.username}} — {{item.display_name}}</mat-option>
          }
        </mat-select>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end"><button mat-button mat-dialog-close>Cancel</button><button mat-flat-button color="primary" [disabled]="user.invalid" (click)="save()">Add</button></mat-dialog-actions>
  `,
  styles: [`.w-100{width:100%;min-width:400px}`],
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule]
})
export class IamMemberDialogComponent {
  protected data = inject<{exclude: string[]}>(MAT_DIALOG_DATA);
  private ref = inject(MatDialogRef<IamMemberDialogComponent>);
  private api = inject(ApiIamService);
  private destroyRef = inject(DestroyRef);
  private notifications = inject(IamNotificationsService);
  protected users = signal<IamUser[]>([]);
  protected search = new FormControl('', {nonNullable: true});
  protected user = new FormControl('', [Validators.required]);
  constructor() {
    this.search.valueChanges.pipe(debounceTime(250), takeUntilDestroyed()).subscribe(() => this.load());
    this.load();
  }
  private load() {
    const excluded = new Set(this.data.exclude);
    this.api.listUsers({page_size: 50, search: this.search.value}).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => this.users.set((result.users ?? []).filter(item => !excluded.has(item.id))),
      error: error => this.notifications.error('Unable to load users', error)
    });
  }
  protected save() { this.ref.close(this.user.value); }
}
