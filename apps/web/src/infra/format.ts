import { applicationLocale, applicationTimeZone } from "../config";

const dateTime = new Intl.DateTimeFormat(applicationLocale, {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: applicationTimeZone,
});
const number = new Intl.NumberFormat(applicationLocale);

export function dateLabel(value: string): string {
  return dateTime.format(new Date(value));
}
export function numberLabel(value: number): string {
  return number.format(value);
}
