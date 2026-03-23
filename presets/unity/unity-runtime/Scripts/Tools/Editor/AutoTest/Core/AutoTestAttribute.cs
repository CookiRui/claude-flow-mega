using System;

namespace {root-namespace}.Tools.AutoTest
{
    [AttributeUsage(AttributeTargets.Class, Inherited = false)]
    public class AutoTestActionAttribute : Attribute
    {
        public string TypeName { get; }
        public AutoTestActionAttribute(string typeName) => TypeName = typeName;
    }

    [AttributeUsage(AttributeTargets.Class, Inherited = false)]
    public class AutoTestConditionAttribute : Attribute
    {
        public string TypeName { get; }
        public AutoTestConditionAttribute(string typeName) => TypeName = typeName;
    }
}
