import {ChangeDetectionStrategy, Component, inject} from '@angular/core';
import {MAT_DIALOG_DATA, MatDialogRef, MatDialogModule} from '@angular/material/dialog';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {MatCheckboxModule} from '@angular/material/checkbox';
import {MatButtonModule} from '@angular/material/button';
import {IamUser} from './iam.models';

@Component({
  selector: 'sm-iam-user-dialog',
  template: `
    <h2 mat-dialog-title>{{ data.user ? 'Edit user' : 'Add user' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="iam-form">
        @if (!data.user) {
          <mat-form-field appearance="outline"><mat-label>Username</mat-label>
            <input matInput formControlName="username" autocomplete="off">
          </mat-form-field>
        }
        <mat-form-field appearance="outline"><mat-label>Display name</mat-label>
          <input matInput formControlName="display_name">
        </mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Email (optional)</mat-label>
          <input matInput formControlName="email" type="email">
        </mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Role</mat-label>
          <mat-select formControlName="role"><mat-option value="user">User</mat-option><mat-option value="admin">Admin</mat-option></mat-select>
        </mat-form-field>
        @if (data.user) {
          <mat-form-field appearance="outline"><mat-label>Status</mat-label>
            <mat-select formControlName="status"><mat-option value="active">Active</mat-option><mat-option value="disabled">Disabled</mat-option></mat-select>
          </mat-form-field>
        } @else {
          <mat-form-field appearance="outline"><mat-label>Temporary password</mat-label>
            <input matInput formControlName="password" type="password" autocomplete="new-password">
          </mat-form-field>
          <mat-form-field appearance="outline"><mat-label>Confirm password</mat-label>
            <input matInput formControlName="confirm_password" type="password" autocomplete="new-password">
          </mat-form-field>
          <mat-checkbox formControlName="must_change_password">Force password change on next login</mat-checkbox>
        }
        @if (error) { <div class="error">{{ error }}</div> }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" (click)="save()" [disabled]="form.invalid">Save</button>
    </mat-dialog-actions>
  `,
  styles: [`.iam-form{display:flex;flex-direction:column;min-width:420px;padding-top:8px}.error{color:var(--color-error);margin-bottom:8px}`],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatCheckboxModule, MatButtonModule]
})
export class IamUserDialogComponent {
  protected data = inject<{user?: IamUser}>(MAT_DIALOG_DATA);
  private ref = inject(MatDialogRef<IamUserDialogComponent>);
  protected error = '';
  protected form = new FormGroup({
    username: new FormControl(this.data.user?.username ?? '', [Validators.required, Validators.pattern(/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$/)]),
    display_name: new FormControl(this.data.user?.display_name ?? '', [Validators.maxLength(128)]),
    email: new FormControl(this.data.user?.email ?? '', [Validators.email]),
    role: new FormControl(this.data.user?.role ?? 'user', [Validators.required]),
    status: new FormControl(this.data.user?.status ?? 'active'),
    password: new FormControl('', this.data.user ? [] : [Validators.required, Validators.minLength(12)]),
    confirm_password: new FormControl('', this.data.user ? [] : [Validators.required]),
    must_change_password: new FormControl(true),
  });

  protected save() {
    const value = this.form.getRawValue();
    if (!this.data.user && value.password !== value.confirm_password) {
      this.error = 'Passwords do not match.';
      return;
    }
    this.ref.close(this.data.user ? {
      display_name: value.display_name,
      email: value.email || null,
      role: value.role,
      status: value.status
    } : {
      username: value.username,
      display_name: value.display_name,
      email: value.email || undefined,
      role: value.role,
      password: value.password,
      must_change_password: value.must_change_password
    });
  }
}

@Component({
  selector: 'sm-iam-password-dialog',
  template: `
    <h2 mat-dialog-title>Reset password</h2>
    <mat-dialog-content>
      <p>Enter a temporary password, or leave blank to generate one.</p>
      <mat-form-field appearance="outline" class="w-100"><mat-label>Temporary password</mat-label>
        <input matInput [formControl]="password" type="password" autocomplete="new-password">
      </mat-form-field>
      @if (password.value && password.invalid) { <div class="error">Password must contain at least 12 characters.</div> }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button color="primary" [disabled]="password.value && password.invalid" (click)="reset()">Reset</button>
    </mat-dialog-actions>
  `,
  styles: [`.w-100{width:100%}.error{color:var(--color-error)}`],
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule]
})
export class IamPasswordDialogComponent {
  private ref = inject(MatDialogRef<IamPasswordDialogComponent>);
  protected password = new FormControl('', [Validators.minLength(12)]);
  protected reset() { this.ref.close(this.password.value || null); }
}
