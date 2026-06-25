# Java 17 Migration Guide

Upgrading to Java 17 (LTS) brings significant performance improvements, language enhancements, and runtime modernization.

## Key Java 17 Language Features
- **Switch Expressions**: Restructured switch block that returns a value and removes fall-through errors.
- **Records**: Concise syntax for immutable data-carrier classes (`public record User(String name, int age) {}`).
- **Pattern Matching for instanceof**: Avoids explicit casting: `if (obj instanceof String s) { System.out.println(s.length()); }`.
- **Sealed Classes**: Restricts which other classes/interfaces may extend or implement them.
- **Text Blocks**: Multi-line string literals using `"""`.

## Removed & Deprecated Features in Java 17
- **Applet API**: Deprecated for removal.
- **RMI Activation**: Removed.
- **Security Manager**: Deprecated for removal in a future release.
- **Garbage Collectors**: CMS (Concurrent Mark Sweep) garbage collector was completely removed in Java 14; use G1 (default) or ZGC instead.

## Migrating from Java 8 / 11 to 17
1. **JDK Internal Access Restriction**: Since Java 9, access to JDK internals is restricted. If your project uses libraries accessing `sun.misc.Unsafe` or other internal APIs, update the libraries or pass `--add-opens` flags.
2. **Removed APIs**: Check for removed APIs like Java EE modules (`javax.xml.bind` / JAXB, etc.). Add standard third-party maven dependencies for JAXB if needed.
3. **Build Plugin Upgrades**: Update `maven-compiler-plugin` to version 3.8.1 or higher and set `<release>17</release>` or `<source>17</source>`/`<target>17</target>`.
