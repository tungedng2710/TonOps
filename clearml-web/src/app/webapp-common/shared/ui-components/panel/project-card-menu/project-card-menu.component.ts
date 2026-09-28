import {ChangeDetectionStrategy, Component, computed, inject, input, output} from '@angular/core';
import {Project} from '~/business-logic/model/projects/project';
import {MenuItemComponent} from '@common/shared/ui-components/panel/menu-item/menu-item.component';
import {MenuComponent} from '@common/shared/ui-components/panel/menu/menu.component';
import {MatDivider} from '@angular/material/divider';
import {Store} from '@ngrx/store';
import {selectCurrentUser} from '@common/core/reducers/users-reducer';
import {isProjectOwner} from '@common/projects/project-permissions';


@Component({
  selector: 'sm-project-card-menu',
  templateUrl: './project-card-menu.component.html',
  styleUrls: ['./project-card-menu.component.scss'],
  changeDetection :ChangeDetectionStrategy.OnPush,
  imports: [
    MenuItemComponent,
    MenuComponent,
    MatDivider
  ]
})
export class ProjectCardMenuComponent {
  private currentUser = inject(Store).selectSignal(selectCurrentUser);
  deleteProjectClicked = output<Project>();
  moveToClicked = output<Project>();
  newProjectClicked = output<Project>();
  projectNameInlineActivated = output();
  projectEditClicked = output<Project>();
  projectSettingsClicked = output<Project>();
  project = input<Project>();
  protected canEdit = computed(() => isProjectOwner(this.project(), this.currentUser()?.id));
}
