import {Component} from '@angular/core';
import {NgOptimizedImage} from '@angular/common';
import {PageBaseComponent} from '@common/enterprise-visibility/page-base.component';

@Component({
    selector: 'sm-genai',
    imports: [
        NgOptimizedImage
    ],
    templateUrl: './genai.component.html',
    styleUrl: '../pages.scss'
})
export class GenaiComponent extends PageBaseComponent {
}
