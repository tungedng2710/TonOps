import {ComponentFixture, TestBed} from '@angular/core/testing';
import {MAT_DIALOG_DATA, MatDialogRef} from '@angular/material/dialog';
import {IamUserDialogComponent} from './iam-user-dialog.component';

describe('IamUserDialogComponent', () => {
  let fixture: ComponentFixture<IamUserDialogComponent>;
  let dialogRef: jasmine.SpyObj<MatDialogRef<IamUserDialogComponent>>;

  beforeEach(async () => {
    dialogRef = jasmine.createSpyObj('MatDialogRef', ['close']);
    await TestBed.configureTestingModule({
      imports: [IamUserDialogComponent],
      providers: [
        {provide: MAT_DIALOG_DATA, useValue: {}},
        {provide: MatDialogRef, useValue: dialogRef}
      ]
    }).compileComponents();
    fixture = TestBed.createComponent(IamUserDialogComponent);
    fixture.detectChanges();
  });

  it('requires matching policy-length passwords', () => {
    const component = fixture.componentInstance;
    component['form'].patchValue({username: 'user01', password: 'short', confirm_password: 'short'});
    expect(component['form'].invalid).toBeTrue();
    component['form'].patchValue({password: 'Temporary-123', confirm_password: 'different-123'});
    component['save']();
    expect(dialogRef.close).not.toHaveBeenCalled();
    expect(component['error']).toContain('match');
  });

  it('returns a valid create-user payload', () => {
    const component = fixture.componentInstance;
    component['form'].patchValue({
      username: 'user01', display_name: 'User One', role: 'user',
      password: 'Temporary-123', confirm_password: 'Temporary-123'
    });
    component['save']();
    expect(dialogRef.close).toHaveBeenCalledWith(jasmine.objectContaining({username: 'user01', role: 'user'}));
  });
});
