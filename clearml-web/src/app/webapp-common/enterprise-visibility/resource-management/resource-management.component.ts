import {Component} from '@angular/core';
import {NgOptimizedImage} from '@angular/common';
import {PageBaseComponent} from '@common/enterprise-visibility/page-base.component';

@Component({
    selector: 'sm-resource-management',
    imports: [
        NgOptimizedImage
    ],
    templateUrl: './resource-management.component.html',
    styleUrl: '../pages.scss'
})
export class ResourceManagementComponent extends PageBaseComponent {
}
