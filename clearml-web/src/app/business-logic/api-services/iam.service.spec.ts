import {TestBed} from '@angular/core/testing';
import {of} from 'rxjs';
import {HTTP} from '~/app.constants';
import {SmApiRequestsService} from './api-requests.service';
import {ApiIamService} from './iam.service';

describe('ApiIamService', () => {
  let service: ApiIamService;
  let requests: jasmine.SpyObj<SmApiRequestsService>;

  beforeEach(() => {
    requests = jasmine.createSpyObj('SmApiRequestsService', ['post']);
    requests.post.and.returnValue(of({}));
    TestBed.configureTestingModule({providers: [ApiIamService, {provide: SmApiRequestsService, useValue: requests}]});
    service = TestBed.inject(ApiIamService);
  });

  it('uses paginated user listing', () => {
    service.listUsers({page: 2, page_size: 25}).subscribe();
    expect(requests.post).toHaveBeenCalledWith(
      `${HTTP.API_BASE_URL}/iam.list_users`,
      {page: 2, page_size: 25},
      jasmine.objectContaining({withCredentials: true})
    );
  });

  it('sends create-user data only to the create endpoint', () => {
    const request = {username: 'user01', password: 'Temporary-123', role: 'user'};
    service.createUser(request).subscribe();
    expect(requests.post).toHaveBeenCalledWith(
      `${HTTP.API_BASE_URL}/iam.create_user`, request, jasmine.any(Object)
    );
  });

  it('uses the public signup endpoint without accepting a role', () => {
    const request = {
      username: 'user01', email: 'user01@example.com',
      display_name: 'User One', password: 'Temporary-123'
    };
    service.signup(request).subscribe();
    expect(requests.post).toHaveBeenCalledWith(
      `${HTTP.API_BASE_URL}/iam.signup`, request, jasmine.any(Object)
    );
    expect('role' in request).toBeFalse();
  });

  it('supports group membership and audit pagination', () => {
    service.addGroupMember('group', 'user').subscribe();
    expect(requests.post).toHaveBeenCalledWith(
      `${HTTP.API_BASE_URL}/iam.add_group_member`,
      {group_id: 'group', user_id: 'user'},
      jasmine.any(Object)
    );
    service.listAudit({page: 0, page_size: 50}).subscribe();
    expect(requests.post).toHaveBeenCalledWith(
      `${HTTP.API_BASE_URL}/iam.list_audit`,
      {page: 0, page_size: 50},
      jasmine.any(Object)
    );
  });
});
