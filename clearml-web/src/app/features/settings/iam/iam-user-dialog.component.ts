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
    <div class="dialog-heading">
      <p class="eyebrow">USER ACCOUNT</p>
      <h2 mat-dialog-title>{{ data.user ? 'Edit user' : 'Add user' }}</h2>
      <p>{{ data.user ? 'Update account details and access.' : 'Create an account for a workspace member.' }}</p>
    </div>
    <mat-dialog-content>
      <form [formGroup]="form" class="iam-form">
        @if (data.user) {
          <div class="account-identifier full-width"><span>Username</span><strong>{{ data.user.username }}</strong></div>
        } @else {
          <mat-form-field appearance="outline" class="full-width"><mat-label>Username</mat-label>
            <input matInput formControlName="username" autocomplete="off">
            @if (form.controls.username.invalid) { <mat-error>Use 3–64 letters, numbers, dots, dashes, or underscores.</mat-error> }
          </mat-form-field>
        }
        <mat-form-field appearance="outline" class="full-width"><mat-label>Display name{{ data.user ? '' : ' (optional)' }}</mat-label>
          <input matInput formControlName="display_name">
          @if (form.controls.display_name.invalid) { <mat-error>Enter a display name of up to 128 characters.</mat-error> }
        </mat-form-field>
        <mat-form-field appearance="outline" class="full-width"><mat-label>Email (optional)</mat-label>
          <input matInput formControlName="email" type="email">
          @if (form.controls.email.invalid) { <mat-error>Enter a valid email address.</mat-error> }
        </mat-form-field>
        <mat-form-field appearance="outline"><mat-label>Role</mat-label>
          <mat-select formControlName="role"><mat-option value="user">User</mat-option><mat-option value="admin">Admin</mat-option></mat-select>
        </mat-form-field>
        @if (data.user) {
          <mat-form-field appearance="outline"><mat-label>Status</mat-label>
            <mat-select formControlName="status"><mat-option value="active">Active</mat-option><mat-option value="disabled">Disabled</mat-option></mat-select>
          </mat-form-field>
        } @else {
          <mat-form-field appearance="outline" class="full-width"><mat-label>Temporary password</mat-label>
            <input matInput formControlName="password" type="password" autocomplete="new-password">
            <mat-hint>At least 12 characters.</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline" class="full-width"><mat-label>Confirm password</mat-label>
            <input matInput formControlName="confirm_password" type="password" autocomplete="new-password">
          </mat-form-field>
          <mat-checkbox class="full-width" formControlName="must_change_password">Require password change at next login</mat-checkbox>
        }
        @if (error) { <div class="error full-width" role="alert">{{ error }}</div> }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end" class="dialog-actions">
      <button mat-button mat-dialog-close>Cancel</button>
      <button mat-flat-button (click)="save()" [disabled]="form.invalid">{{ data.user ? 'Save changes' : 'Add user' }}</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .dialog-heading { padding: 24px 24px 8px; }
    .eyebrow { margin: 0 0 8px; color: var(--color-primary); font-size: 11px; font-weight: 700; letter-spacing: .12em; }
    h2[mat-dialog-title] { margin: 0 0 6px; padding: 0; font-size: 24px; }
    .dialog-heading > p:last-child { margin: 0; color: var(--color-on-surface-variant); font-size: 13px; }
    .iam-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 16px; padding-top: 12px; }
    .iam-form mat-form-field { min-width: 0; }
    .full-width { grid-column: 1 / -1; }
    .account-identifier { display: flex; flex-direction: column; gap: 5px; margin-bottom: 6px; padding: 12px 14px; border-radius: 10px; background: var(--color-surface-container-low); }
    .account-identifier span { color: var(--color-on-surface-variant); font-size: 11px; }
    .account-identifier strong { font-size: 14px; }
    .error { color: var(--color-error); font-size: 13px; }
    .dialog-actions { gap: 8px; padding: 16px 24px 24px; border-top: 1px solid var(--color-outline-variant); }
    @media (max-width: 480px) { .iam-form { grid-template-columns: minmax(0, 1fr); } }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatCheckboxModule, MatButtonModule]
})
export class IamUserDialogComponent {
  protected data = inject<{user?: IamUser}>(MAT_DIALOG_DATA);
  private ref = inject(MatDialogRef<IamUserDialogComponent>);
  protected error = '';
  protected form = new FormGroup({
    username: new FormControl(this.data.user?.username ?? '', [Validators.required, Validators.pattern(/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$/)]),
    display_name: new FormControl(this.data.user?.display_name ?? '', this.data.user ? [Validators.required, Validators.maxLength(128)] : [Validators.maxLength(128)]),
    email: new FormControl(this.data.user?.email ?? '', [Validators.email]),
    role: new FormControl(this.data.user?.role ?? 'user', [Validators.required]),
    status: new FormControl(this.data.user?.status ?? 'active'),
    password: new FormControl('', this.data.user ? [] : [Validators.required, Validators.minLength(12)]),
    confirm_password: new FormControl('', this.data.user ? [] : [Validators.required]),
    must_change_password: new FormControl(true),
  });

  protected save() {
    this.form.markAllAsTouched();
    if (this.form.invalid) return;
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
