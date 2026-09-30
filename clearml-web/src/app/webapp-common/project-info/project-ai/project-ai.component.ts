import {afterRenderEffect, ChangeDetectionStrategy, Component, computed, DestroyRef, effect, ElementRef, inject, input, signal, untracked, viewChild} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {MatButton} from '@angular/material/button';
import {MatIcon} from '@angular/material/icon';
import {MatProgressSpinner} from '@angular/material/progress-spinner';
import {HttpErrorResponse} from '@angular/common/http';
import {Subscription} from 'rxjs';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {marked} from 'marked';
import DOMPurify from 'dompurify';
import {Project} from '~/business-logic/model/projects/project';
import {ApiProjectAiService, ProjectAiResponse} from '~/business-logic/api-services/project-ai.service';

interface AiMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  html?: string;
  report?: boolean;
  title?: string;
  details?: ProjectAiResponse;
  saved?: {id: string; project_id: string};
}

@Component({
  selector: 'sm-project-ai',
  templateUrl: './project-ai.component.html',
  styleUrl: './project-ai.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, RouterLink, MatButton, MatIcon, MatProgressSpinner]
})
export class ProjectAiComponent {
  project = input.required<Project>();
  protected prompt = signal('');
  protected messages = signal<AiMessage[]>([]);
  protected busy = signal(false);
  protected saving = signal<number | null>(null);
  protected error = signal('');
  protected suggestions = ['Summarize task progress', 'Compare validation metrics', 'Which tasks need attention?'];
  private api = inject(ApiProjectAiService);
  private destroyRef = inject(DestroyRef);
  private request?: Subscription;
  private saveRequest?: Subscription;
  private nextId = 0;
  private projectId = computed(() => this.project()?.id);
  private conversation = viewChild<ElementRef<HTMLElement>>('conversation');

  constructor() {
    effect(() => {
      this.projectId();
      untracked(() => {
        this.request?.unsubscribe();
        this.saveRequest?.unsubscribe();
        this.messages.set([]);
        this.prompt.set('');
        this.busy.set(false);
        this.saving.set(null);
        this.error.set('');
      });
    });
    afterRenderEffect(() => {
      this.messages().length;
      const container = this.conversation()?.nativeElement;
      const latest = container?.lastElementChild as HTMLElement;
      if (latest) container.scrollTop = latest.offsetTop - container.offsetTop;
    });
  }

  protected send(report = false, suggestion?: string) {
    if (this.busy()) return;
    const question = (suggestion ?? this.prompt()).trim();
    if (!question && !report) return;
    const history = this.messages().slice(-8).map(message => ({role: message.role, content: message.content.slice(0, 3000)}));
    this.messages.update(messages => [...messages, {
      id: ++this.nextId, role: 'user', content: question || 'Generate a project report'
    }]);
    this.prompt.set('');
    this.error.set('');
    this.busy.set(true);
    this.request = this.api.ask(this.project().id, question, history, report)
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: response => {
          const html = DOMPurify.sanitize(marked.parse(response.content, {async: false}) as string, {
            FORBID_TAGS: ['img', 'iframe', 'script', 'style', 'video', 'audio', 'object', 'embed', 'form'],
            FORBID_ATTR: ['style']
          });
          this.messages.update(messages => [...messages, {
            id: ++this.nextId, role: 'assistant', content: response.content, html,
            report, title: response.title, details: response
          }]);
          this.busy.set(false);
        },
        error: error => {
          this.error.set(this.errorMessage(error));
          this.busy.set(false);
        }
      });
  }

  protected cancel() {
    this.request?.unsubscribe();
    this.busy.set(false);
  }

  protected clear() {
    this.messages.set([]);
    this.error.set('');
  }

  protected updateTitle(id: number, title: string) {
    this.messages.update(messages => messages.map(message => message.id === id ? {...message, title} : message));
  }

  protected save(message: AiMessage) {
    if (this.saving() !== null || message.saved || !message.details?.can_save || (message.title?.trim().length || 0) < 3) return;
    this.saving.set(message.id);
    this.error.set('');
    this.saveRequest = this.api.saveReport(this.project().id, message.title.trim(), message.content)
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: saved => {
          this.messages.update(messages => messages.map(item => item.id === message.id ? {...item, saved} : item));
          this.saving.set(null);
        },
        error: error => {
          this.error.set(this.errorMessage(error));
          this.saving.set(null);
        }
      });
  }

  private errorMessage(error: HttpErrorResponse) {
    if (error.status === 0) return 'Could not connect to the server. Please try again.';
    return error.error?.meta?.result_msg || 'Unable to complete the AI request. Please try again.';
  }
}
