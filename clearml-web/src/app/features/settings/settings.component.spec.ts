import {signal} from '@angular/core';
import {ComponentFixture, TestBed} from '@angular/core/testing';
import {provideRouter} from '@angular/router';
import {Store} from '@ngrx/store';
import {SettingsComponent} from './settings.component';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {User} from '~/business-logic/model/users/user';
import {of} from 'rxjs';

describe('SettingsComponent IAM menu', () => {
  let fixture: ComponentFixture<SettingsComponent>;
  const currentUser = signal<User>({id: 'admin', role: 'admin'});

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [
        provideRouter([]),
        {provide: Store, useValue: {selectSignal: () => currentUser}},
        {provide: ApiIamService, useValue: {status: () => of({enabled: true})}}
      ]
    }).compileComponents();
    fixture = TestBed.createComponent(SettingsComponent);
  });

  it('shows User Management only to administrators', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('User Management');
    currentUser.set({id: 'user', role: 'user'});
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('User Management');
  });
});
