import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {Store} from '@ngrx/store';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';
import {updateCurrentUser} from '@common/core/actions/users.actions';
import {GetCurrentUserResponseUserObject} from '~/business-logic/model/users/getCurrentUserResponseUserObject';
import {addMessage} from '@common/core/actions/layout.actions';
import {ConfigurationService} from '@common/shared/services/configuration.service';
import {InlineEditComponent} from '@common/shared/ui-components/inputs/inline-edit/inline-edit.component';
import {IdBadgeComponent} from '@common/shared/components/id-badge/id-badge.component';
import {setAllProjectUsers} from '@common/core/actions/projects.actions';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatButtonModule} from '@angular/material/button';
import {ApiIamService} from '~/business-logic/api-services/iam.service';

@Component({
  selector: 'sm-profile-name',
  templateUrl: './profile-name.component.html',
  styleUrls: ['./profile-name.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    InlineEditComponent,
    IdBadgeComponent,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule
  ]
})
export class ProfileNameComponent {
  private store = inject(Store);
  protected readonly config = inject(ConfigurationService);
  private iam = inject(ApiIamService);

  currentUser = this.store.selectSignal(selectCurrentUser);
  active = signal(false);
  iamEnabled = signal(false);
  passwordMessage = signal('');
  passwordError = signal('');
  passwordForm = new FormGroup({
    current: new FormControl('', [Validators.required]),
    password: new FormControl('', [Validators.required, Validators.minLength(12)]),
    confirm: new FormControl('', [Validators.required])
  });

  constructor() {
    this.iam.status().subscribe({
      next: result => this.iamEnabled.set(result.enabled),
      error: () => this.iamEnabled.set(false)
    });
  }


  nameChange(updatedUserName: string, currentUser: GetCurrentUserResponseUserObject) {
    const user = {name: updatedUserName, user: currentUser.id};
    this.store.dispatch(updateCurrentUser({user}));
    this.store.dispatch(setAllProjectUsers({users: []}));
  }
  copyToClipboard() {
    this.store.dispatch(addMessage('success', 'Copied to clipboard'));
  }

  changePassword() {
    const value = this.passwordForm.getRawValue();
    this.passwordMessage.set('');
    this.passwordError.set('');
    if (value.password !== value.confirm) {
      this.passwordError.set('New passwords do not match.');
      return;
    }
    this.iam.changePassword(value.current, value.password).subscribe({
      next: () => {
        this.passwordForm.reset();
        this.passwordMessage.set('Password changed successfully.');
      },
      error: error => this.passwordError.set(error?.error?.meta?.result_msg ?? 'Unable to change password.')
    });
  }
}
