/**
 * @name Annotation Values
 * @description Extracts annotation parameter values from methods and fields.
 *              Critical for BVA test generation — provides @Min(18), @Max(150) values.
 * @kind table
 * @id java/annotation-values
 */
import java

from Annotatable target, Annotation a, string elementName
where (target instanceof Method or target instanceof Field or target instanceof Parameter)
  and target.(Method).fromSource()
  and a = target.getAnAnnotation()
  and a.getType().fromSource() = false  // standard annotations
  and elementName = a.getAValue().getElement().getName()
select
  target.(Method).getDeclaringType().getQualifiedName()  as class_name,
  target.(Method).getName()                              as method_name,
  a.getType().getName()                                  as annotation_name,
  elementName                                            as element_name,
  a.getValue(elementName).toString()                     as element_value
