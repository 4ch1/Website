namespace IIS.Models.Tickets
{
    public class Category
    {
        public CategoryEnum TypeEnum;

        public Category(CategoryEnum category)
        {
            TypeEnum = category;
        }

        public string FullName => TypeEnum == CategoryEnum.BUSINESS ? "Business class" : "Economy class";
        public string ShortName => TypeEnum == CategoryEnum.BUSINESS ? "Business" : "Economy";
    }

    public enum CategoryEnum
    {
        BUSINESS,
        ECONOMY
    }
}