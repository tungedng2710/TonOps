import {Component, DestroyRef, inject, signal} from '@angular/core';
import {DatePipe, DOCUMENT} from '@angular/common';
import {takeUntilDestroyed} from '@angular/core/rxjs-interop';
import {FormControl, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {MatButtonModule} from '@angular/material/button';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {ApiDataStudioService, DataStudioConnection, DataStudioDataset, DataStudioRevision} from '~/business-logic/api-services/datastudio.service';

@Component({
  selector: 'sm-datastudio-settings',
  templateUrl: './datastudio.component.html',
  styleUrls: ['./datastudio.component.scss'],
  imports: [DatePipe, ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule]
})
export class DataStudioComponent {
  private api = inject(ApiDataStudioService);
  private destroyRef = inject(DestroyRef);
  private document = inject(DOCUMENT);
  protected connection = signal<DataStudioConnection | null>(null);
  protected datasets = signal<DataStudioDataset[]>([]);
  protected revisions = signal<DataStudioRevision[]>([]);
  protected selected = signal<DataStudioDataset | null>(null);
  protected busy = signal(true);
  protected loaded = signal(false);
  protected error = signal('');
  protected message = signal('');
  protected form = new FormGroup({
    username: new FormControl('', {nonNullable: true, validators: [Validators.required, Validators.pattern(/^[a-z0-9][a-z0-9_-]{0,63}$/i)]}),
    token: new FormControl('', {nonNullable: true, validators: [Validators.required, Validators.pattern(/^ds_pat_[A-Za-z0-9_-]{20,200}$/)]})
  });

  constructor() {
    this.api.status().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: connection => {
        this.connection.set(connection);
        this.form.controls.username.setValue(connection.username ?? '');
        this.busy.set(false);
        if (connection.connected) this.refresh();
      },
      error: error => this.fail(error, 'Unable to load your DataStudio connection.')
    });
  }

  protected connect() {
    if (this.form.invalid || this.busy() || !this.connection()?.configured) return;
    const {username, token} = this.form.getRawValue();
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    const request = this.api.connect(username.trim(), token.trim());
    this.form.controls.token.reset();
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: connection => {
        this.connection.set(connection);
        this.form.controls.username.setValue(connection.username ?? '');
        this.selected.set(null);
        this.revisions.set([]);
        this.datasets.set([]);
        this.loaded.set(false);
        this.message.set(`Connected as ${connection.username}.`);
        this.busy.set(false);
        this.refresh();
      },
      error: error => this.fail(error, 'Unable to connect to DataStudio.')
    });
  }

  protected refresh() {
    if (this.busy() || !this.connection()?.connected) return;
    this.busy.set(true);
    this.error.set('');
    this.selected.set(null);
    this.revisions.set([]);
    this.api.datasets().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => {
        this.datasets.set(result.items);
        this.connection.set(result.connection);
        this.loaded.set(true);
        this.busy.set(false);
      },
      error: error => {
        this.datasets.set([]);
        this.loaded.set(false);
        this.fail(error, 'Unable to load DataStudio datasets.');
      }
    });
  }

  protected disconnect() {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    this.api.disconnect().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: connection => {
        this.connection.set(connection);
        this.datasets.set([]);
        this.revisions.set([]);
        this.selected.set(null);
        this.form.reset();
        this.loaded.set(false);
        this.message.set('DataStudio disconnected.');
        this.busy.set(false);
      },
      error: error => this.fail(error, 'Unable to disconnect DataStudio.')
    });
  }

  protected showRevisions(dataset: DataStudioDataset) {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.selected.set(dataset);
    this.revisions.set([]);
    this.api.revisions(dataset.namespace, dataset.slug).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => { this.revisions.set(result.revisions); this.busy.set(false); },
      error: error => { this.selected.set(null); this.fail(error, 'Unable to load dataset revisions.'); }
    });
  }

  protected datasetUrl(dataset: DataStudioDataset, revision?: string): string {
    const base = new URL(this.connection()?.web_url ?? 'http://localhost:3000');
    const browserHost = this.document.location?.hostname;
    if (['localhost', '127.0.0.1'].includes(base.hostname) && browserHost) base.hostname = browserHost;
    const url = new URL(`${base.href.replace(/\/$/, '')}/datasets/${encodeURIComponent(dataset.namespace)}/${encodeURIComponent(dataset.slug)}`);
    if (revision) url.searchParams.set('revision', revision);
    return url.href;
  }

  private fail(error: {error?: {meta?: {result_msg?: string}}}, fallback: string) {
    this.error.set(error?.error?.meta?.result_msg ?? fallback);
    this.busy.set(false);
  }
}
