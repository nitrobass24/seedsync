import { Pipe, PipeTransform } from "@angular/core";

@Pipe({name: "capitalize", standalone: true})
export class CapitalizePipe implements PipeTransform {

    transform(value: unknown) {
        if (typeof value === 'string' && value) {
            const spaced = value.replace(/_/g, ' ');
            return spaced.charAt(0).toUpperCase() + spaced.slice(1);
        }
        return value;
    }

}
