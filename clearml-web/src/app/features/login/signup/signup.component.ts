import {ChangeDetectionStrategy, Component, inject, signal} from '@angular/core';
import {HttpErrorResponse} from '@angular/common/http';
import {NgOptimizedImage} from '@angular/common';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {MatButtonModule} from '@angular/material/button';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {Title} from '@angular/platform-browser';
import {finalize} from 'rxjs/operators';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {ConfigurationService} from '@common/shared/services/configuration.service';
import {Error as ApiError, ErrorService} from '@common/shared/services/error.service';

@Component({
  selector: 'sm-signup',
  templateUrl: './signup.component.html',
  styleUrls: ['./signup.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    NgOptimizedImage,
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule
  ]
})
export class SignupComponent {
  private iam = inject(ApiIamService);
  private errorService = inject(ErrorService);
  private title = inject(Title);
  protected environment = inject(ConfigurationService).configuration;

  protected checkingAvailability = signal(true);
  protected signupEnabled = signal(false);
  protected submitting = signal(false);
  protected complete = signal(false);
  protected error = signal('');

  protected form = new FormGroup({
    username: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$/)]
    }),
    display_name: new FormControl('', {nonNullable: true, validators: [Validators.maxLength(128)]}),
    email: new FormControl('', {nonNullable: true, validators: [Validators.required, Validators.email, Validators.maxLength(254)]}),
    password: new FormControl('', {nonNullable: true, validators: [Validators.required, Validators.minLength(12), Validators.maxLength(128)]}),
    confirm_password: new FormControl('', {nonNullable: true, validators: [Validators.required]})
  });

  protected passwordsMatch() {
    const value = this.form.getRawValue();
    return !value.confirm_password || value.password === value.confirm_password;
  }

  constructor() {
    this.title.setTitle('TonOps - Create account');
    this.iam.status().subscribe({
      next: status => {
        this.signupEnabled.set(status.enabled && status.self_signup_enabled);
        this.checkingAvailability.set(false);
      },
      error: () => {
        this.signupEnabled.set(false);
        this.checkingAvailability.set(false);
      }
    });
  }

  protected signup() {
    this.error.set('');
    this.form.markAllAsTouched();
    if (this.form.invalid || !this.passwordsMatch()) {
      return;
    }

    const value = this.form.getRawValue();
    this.submitting.set(true);
    this.iam.signup({
      username: value.username.trim(),
      display_name: value.display_name.trim() || undefined,
      email: value.email.trim(),
      password: value.password
    }).pipe(
      finalize(() => this.submitting.set(false))
    ).subscribe({
      next: () => {
        this.form.reset();
        this.complete.set(true);
      },
      error: (response: HttpErrorResponse) => {
        const detail = this.errorService.getErrorMsg(response.error as ApiError);
        this.error.set(detail || 'We could not create your account. Please try again.');
      }
    });
  }
}
