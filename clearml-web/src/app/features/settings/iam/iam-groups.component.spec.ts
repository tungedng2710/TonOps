import {ComponentFixture, TestBed} from '@angular/core/testing';
import {provideNoopAnimations} from '@angular/platform-browser/animations';
import {MatDialog, MatDialogRef} from '@angular/material/dialog';
import {of} from 'rxjs';
import {ApiIamService} from '~/business-logic/api-services/iam.service';
import {IamGroupsComponent} from './iam-groups.component';
import {IamNotificationsService} from './iam-notifications.service';

describe('IamGroupsComponent', () => {
  let fixture: ComponentFixture<IamGroupsComponent>;
  let api: jasmine.SpyObj<ApiIamService>;
  let dialog: jasmine.SpyObj<MatDialog>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<ApiIamService>('ApiIamService', ['listGroups', 'createGroup']);
    api.listGroups.and.returnValue(of({
      groups: [{id: 'g1', name: 'cv-team', description: 'CV Engineers', member_count: 2}],
      total: 1, page: 0, page_size: 200
    }));
    api.createGroup.and.returnValue(of({group: {id: 'g2', name: 'ml-team', member_count: 0}}));
    dialog = jasmine.createSpyObj<MatDialog>('MatDialog', ['open']);
    dialog.open.and.returnValue({afterClosed: () => of({name: 'ml-team', description: ''})} as MatDialogRef<unknown>);
    await TestBed.configureTestingModule({
      imports: [IamGroupsComponent],
      providers: [
        provideNoopAnimations(),
        {provide: ApiIamService, useValue: api},
        {provide: MatDialog, useValue: dialog},
        {provide: IamNotificationsService, useValue: {error: jasmine.createSpy('error')}}
      ]
    }).compileComponents();
    fixture = TestBed.createComponent(IamGroupsComponent);
    fixture.detectChanges();
  });

  it('renders groups and creates a group from the dialog', () => {
    expect(fixture.nativeElement.textContent).toContain('cv-team');
    fixture.componentInstance['editGroup']();
    expect(api.createGroup).toHaveBeenCalledWith({name: 'ml-team', description: ''});
  });
});
