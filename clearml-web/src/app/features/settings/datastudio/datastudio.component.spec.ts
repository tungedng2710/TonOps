import {ComponentFixture, TestBed} from '@angular/core/testing';
import {of, Subject, throwError} from 'rxjs';
import {ApiDataStudioService, DataStudioConnection, DataStudioDataset} from '~/business-logic/api-services/datastudio.service';
import {DataStudioComponent} from './datastudio.component';

describe('DataStudio settings', () => {
  let fixture: ComponentFixture<DataStudioComponent>;
  let api: jasmine.SpyObj<ApiDataStudioService>;
  const disconnected: DataStudioConnection = {configured: true, connected: false, username: null, checked_at: null, web_url: 'http://localhost:3000'};
  const connected: DataStudioConnection = {...disconnected, connected: true, username: 'alice', checked_at: '2026-10-14T01:00:00Z'};
  const dataset: DataStudioDataset = {id: 'repo', namespace: 'alice', slug: 'vehicles', description: 'Vehicle example', visibility: 'private', data_stage: 'training_ready', tags: [], updated_at: '', latest_revision: null};

  beforeEach(async () => {
    api = jasmine.createSpyObj<ApiDataStudioService>('ApiDataStudioService', ['status', 'connect', 'disconnect', 'datasets', 'revisions']);
    api.status.and.returnValue(of(disconnected));
    api.connect.and.returnValue(of(connected));
    api.disconnect.and.returnValue(of(disconnected));
    api.datasets.and.returnValue(of({items: [dataset], connection: connected}));
    api.revisions.and.returnValue(of({revisions: [{revision_id: 'abc123', status: 'ready', data_stage: 'training_ready', commit_message: 'Example', created_at: '', manifest_sha256: 'abc'}]}));
    await TestBed.configureTestingModule({imports: [DataStudioComponent], providers: [{provide: ApiDataStudioService, useValue: api}]}).compileComponents();
    fixture = TestBed.createComponent(DataStudioComponent);
    fixture.detectChanges();
  });

  it('clears the token before the connection request completes and loads datasets', () => {
    const pending = new Subject<DataStudioConnection>();
    api.connect.and.returnValue(pending);
    fixture.componentInstance['form'].setValue({username: 'alice', token: 'ds_pat_' + 'a'.repeat(40)});
    fixture.componentInstance['connect']();
    expect(fixture.componentInstance['form'].controls.token.value).toBe('');
    expect(api.connect).toHaveBeenCalledWith('alice', 'ds_pat_' + 'a'.repeat(40));
    pending.next(connected);
    pending.complete();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('alice/vehicles');
    expect(fixture.nativeElement.textContent).toContain('Connected as');
  });

  it('shows rejected credentials and requires a fresh token', () => {
    api.connect.and.returnValue(throwError(() => ({error: {meta: {result_msg: 'DataStudio rejected the token.'}}})));
    fixture.componentInstance['form'].setValue({username: 'alice', token: 'ds_pat_' + 'a'.repeat(40)});
    fixture.componentInstance['connect']();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('DataStudio rejected the token.');
    expect(fixture.componentInstance['form'].controls.token.value).toBe('');
    expect(api.datasets).not.toHaveBeenCalled();
  });

  it('loads pinned revision links and clears datasets after disconnecting', () => {
    fixture.componentInstance['form'].setValue({username: 'alice', token: 'ds_pat_' + 'a'.repeat(40)});
    fixture.componentInstance['connect']();
    fixture.componentInstance['showRevisions'](dataset);
    fixture.detectChanges();
    expect(api.revisions).toHaveBeenCalledWith('alice', 'vehicles');
    const links = Array.from(fixture.nativeElement.querySelectorAll('a')) as HTMLAnchorElement[];
    expect(links.some(link => new URL(link.href).searchParams.get('revision') === 'abc123')).toBeTrue();
    fixture.componentInstance['disconnect']();
    fixture.detectChanges();
    expect(fixture.componentInstance['datasets']()).toEqual([]);
    expect(fixture.componentInstance['selected']()).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('DataStudio disconnected.');
  });
});
