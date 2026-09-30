import {inject, Injectable} from '@angular/core';
import {HttpHeaders} from '@angular/common/http';
import {HTTP} from '~/app.constants';
import {SmApiRequestsService} from './api-requests.service';

export interface ProjectAiHistory {
  role: 'user' | 'assistant';
  content: string;
}

export interface ProjectAiResponse {
  content: string;
  title: string;
  can_save: boolean;
  context: {total_tasks: number; included_tasks: number; omitted_tasks: number; generated_at: string};
  sources: {id: string; name: string; project_id: string}[];
}

@Injectable({providedIn: 'root'})
export class ApiProjectAiService {
  private api = inject(SmApiRequestsService);
  private options = {headers: new HttpHeaders({'Accept': 'application/json'}), withCredentials: true};

  ask(project: string, question: string, history: ProjectAiHistory[], report = false) {
    return this.api.post<ProjectAiResponse>(`${HTTP.API_BASE_URL}/project_ai.${report ? 'generate_report' : 'ask'}`,
      {project, ...(question && {question}), history}, this.options);
  }

  saveReport(project: string, title: string, content: string) {
    return this.api.post<{id: string; project_id: string}>(`${HTTP.API_BASE_URL}/project_ai.save_report`,
      {project, title, content}, this.options);
  }
}
