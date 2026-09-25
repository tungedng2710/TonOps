import {ChangeDetectionStrategy, Component, effect, inject, signal} from '@angular/core';
import {Store} from '@ngrx/store';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatButtonModule} from '@angular/material/button';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';
import {fetchCurrentUser} from '@common/core/actions/users.actions';
import {ApiUsersService} from '~/business-logic/api-services/users.service';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {selectUserTheme} from '@common/core/reducers/view.reducer';
import {userThemeChanged} from '@common/core/actions/layout.actions';

@Component({
  selector: 'sm-profile-name',
  templateUrl: './profile-name.component.html',
  styleUrls: ['./profile-name.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule]
})
export class ProfileNameComponent {
  private store = inject(Store);
  private users = inject(ApiUsersService);
  private iam = inject(ApiIamService);
  currentUser = this.store.selectSignal(selectCurrentUser);
  iamEnabled = signal(false);
  saving = signal(false);
  savingPassword = signal(false);
  userTheme = this.store.selectSignal(selectUserTheme);
  themeOptions = [
    {value: 'light', label: 'Light', description: 'Bright and clear'},
    {value: 'dark', label: 'Dark', description: 'Easy on the eyes'},
    {value: 'system', label: 'System', description: 'Match this device'}
  ] as const;
  profileMessage = signal('');
  profileError = signal('');
  passwordMessage = signal('');
  passwordError = signal('');
  profileForm = new FormGroup({
    name: new FormControl('', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]),
    given_name: new FormControl('', [Validators.maxLength(120)]),
    family_name: new FormControl('', [Validators.maxLength(120)]),
    avatar: new FormControl('', [Validators.maxLength(2048), Validators.pattern(/^(https?:\/\/.*)?$/)]),
    bio: new FormControl('', [Validators.maxLength(1000)])
  });
  passwordForm = new FormGroup({
    current: new FormControl('', [Validators.required]),
    password: new FormControl('', [Validators.required, Validators.minLength(12)]),
    confirm: new FormControl('', [Validators.required])
  });

  constructor() {
    effect(() => {
      const user = this.currentUser();
      if (user && !this.profileForm.dirty) {
        this.profileForm.patchValue({name: user.name ?? '', given_name: user.given_name ?? '', family_name: user.family_name ?? '', avatar: user.avatar ?? '', bio: user.bio ?? ''}, {emitEvent: false});
      }
    });
    this.iam.status().subscribe({
      next: result => this.iamEnabled.set(result.enabled),
      error: () => this.iamEnabled.set(false)
    });
  }

  saveProfile() {
    const user = this.currentUser();
    if (!user?.id || this.profileForm.invalid || this.saving()) return;
    this.saving.set(true);
    this.profileMessage.set('');
    this.profileError.set('');
    const {name, given_name, family_name, avatar, bio} = this.profileForm.getRawValue();
    this.users.usersUpdate({user: user.id, name: name.trim(), given_name: given_name.trim(), family_name: family_name.trim(), avatar: avatar.trim(), bio: bio.trim()}).subscribe({
      next: () => {
        this.saving.set(false);
        this.profileForm.markAsPristine();
        this.profileMessage.set('Profile saved.');
        this.store.dispatch(fetchCurrentUser());
      },
      error: error => {
        this.saving.set(false);
        this.profileError.set(error?.error?.meta?.result_msg ?? 'Unable to save profile.');
      }
    });
  }

  changePassword() {
    if (this.passwordForm.invalid || this.savingPassword()) return;
    const value = this.passwordForm.getRawValue();
    this.passwordMessage.set('');
    this.passwordError.set('');
    if (value.password !== value.confirm) {
      this.passwordError.set('New passwords do not match.');
      return;
    }
    this.savingPassword.set(true);
    this.iam.changePassword(value.current, value.password).subscribe({
      next: () => {
        this.savingPassword.set(false);
        this.passwordForm.reset();
        this.passwordMessage.set('Password changed successfully.');
      },
      error: error => {
        this.savingPassword.set(false);
        this.passwordError.set(error?.error?.meta?.result_msg ?? 'Unable to change password.');
      }
    });
  }

  setTheme(theme: 'light' | 'dark' | 'system') {
    this.store.dispatch(userThemeChanged({theme}));
  }
}
