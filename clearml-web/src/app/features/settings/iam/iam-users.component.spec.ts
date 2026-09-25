import {ComponentFixture, TestBed} from '@angular/core/testing';
import {provideNoopAnimations} from '@angular/platform-browser/animations';
import {MatDialog, MatDialogRef} from '@angular/material/dialog';
import {of} from 'rxjs';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {IamNotificationsService} from './iam-notifications.service';
import {IamUsersComponent} from './iam-users.component';
import {IamUser} from './iam.models';

describe('IamUsersComponent', () => {
  const user: IamUser = {
    id: 'u1', username: 'user01', display_name: 'User One', role: 'user', status: 'active',
    must_change_password: false, created_at: '2026-01-01T00:00:00Z'
  };
  let fixture: ComponentFixture<IamUsersComponent>;
  let api: jasmine.SpyObj<ApiIamService>;
  let dialog: jasmine.SpyObj<MatDialog>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<ApiIamService>('ApiIamService', ['listUsers', 'disableUser', 'enableUser']);
    api.listUsers.and.returnValue(of({users: [user], total: 1, page: 0, page_size: 50}));
    api.disableUser.and.returnValue(of({user}));
    dialog = jasmine.createSpyObj<MatDialog>('MatDialog', ['open']);
    dialog.open.and.returnValue({afterClosed: () => of({isConfirmed: true})} as MatDialogRef<unknown>);
    await TestBed.configureTestingModule({
      imports: [IamUsersComponent],
      providers: [
        provideNoopAnimations(),
        {provide: ApiIamService, useValue: api},
        {provide: MatDialog, useValue: dialog},
        {provide: IamNotificationsService, useValue: {error: jasmine.createSpy('error')}}
      ]
    }).compileComponents();
    fixture = TestBed.createComponent(IamUsersComponent);
    fixture.detectChanges();
  });

  it('renders returned users', () => {
    expect(fixture.nativeElement.textContent).toContain('user01');
    expect(fixture.nativeElement.textContent).toContain('User One');
  });

  it('requires confirmation before disabling a user', () => {
    fixture.componentInstance['toggle'](user);
    expect(dialog.open).toHaveBeenCalled();
    expect(api.disableUser).toHaveBeenCalledWith('u1');
  });
});
