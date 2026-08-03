/**
 * @name Method Signatures
 * @description Extracts all method signatures with fully resolved return types
 *              and declaring class info — for enriching kb.json.
 * @kind table
 * @id java/method-signatures
 */
import java

from Method m
where m.fromSource()
  and not m.getDeclaringType() instanceof AnonymousClass
select
  m.getDeclaringType().getQualifiedName()  as declaring_class,
  m.getName()                              as method_name,
  m.getReturnType().toString()             as return_type,
  m.getFile().getRelativePath()            as file_path,
  m.getLocation().getStartLine()           as line_start,
  m.getLocation().getEndLine()             as line_end,
  concat(m.getDeclaringType().getPackage().getName(), ".", m.getDeclaringType().getName(), ".", m.getName()) as qualified_name
